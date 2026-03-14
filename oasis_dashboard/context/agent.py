from __future__ import annotations

import inspect
import time
from typing import Any, Optional, Union

from camel.memories import MemoryRecord
from camel.messages import BaseMessage
from camel.models import BaseModelBackend, ModelManager
from camel.toolkits import FunctionTool
from camel.types import OpenAIBackendRole
from oasis.social_agent.agent import SocialAgent
from oasis.social_platform import Channel
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType

from .config import ContextRuntimeSettings
from .environment import ContextSocialEnvironment
from .memory import build_chat_history_memory


class ContextSocialAgent(SocialAgent):
    def __init__(
        self,
        agent_id: int,
        user_info: UserInfo,
        user_info_template=None,
        channel: Channel | None = None,
        model: Optional[
            Union[BaseModelBackend, list[BaseModelBackend], ModelManager]
        ] = None,
        agent_graph=None,
        available_actions: list[ActionType] | None = None,
        tools: Optional[list[Union[FunctionTool, Any]]] = None,
        max_iteration: int = 1,
        interview_record: bool = False,
        context_settings: ContextRuntimeSettings | None = None,
    ):
        if context_settings is None:
            raise ValueError("context_settings is required for ContextSocialAgent.")

        self.context_settings = context_settings
        super().__init__(
            agent_id=agent_id,
            user_info=user_info,
            user_info_template=user_info_template,
            channel=channel,
            model=model,
            agent_graph=agent_graph,
            available_actions=available_actions,
            tools=tools,
            max_iteration=max_iteration,
            interview_record=interview_record,
        )

        original_action = self.env.action
        actionable_tool_names = {
            tool.func.__name__
            for tool in (self.action_tools or [])
            if hasattr(tool, "func")
        }
        self.env = ContextSocialEnvironment(
            action=original_action,
            runtime_settings=context_settings,
            actionable_tool_names=actionable_tool_names,
        )
        self.memory = build_chat_history_memory(
            token_counter=context_settings.token_counter,
            context_token_limit=context_settings.context_token_limit,
            agent_id=self.agent_id,
            window_size=context_settings.memory_window_size,
        )
        self._ensure_system_message_in_memory()
        self.prune_tool_calls_from_memory = True

    def update_memory(self, *args, **kwargs):
        parent_method = super().update_memory
        try:
            bound = inspect.signature(parent_method).bind_partial(*args, **kwargs)
        except TypeError:
            return parent_method(*args, **kwargs)

        if set(bound.arguments) - {"message", "role", "timestamp"}:
            return parent_method(*args, **kwargs)

        message = bound.arguments.get("message")
        role = bound.arguments.get("role")
        timestamp = bound.arguments.get("timestamp")
        if not isinstance(message, BaseMessage) or role is None:
            return parent_method(*args, **kwargs)

        if not self._message_fits_context_limit(message, role):
            return parent_method(*args, **kwargs)

        self.memory.write_record(
            MemoryRecord(
                message=message,
                role_at_backend=role,
                timestamp=(
                    timestamp
                    if timestamp is not None
                    else time.time_ns() / 1_000_000_000
                ),
                agent_id=self.agent_id,
            )
        )
        return None

    def _message_fits_context_limit(
        self,
        message: BaseMessage,
        role: OpenAIBackendRole,
    ) -> bool:
        messages = []
        if (
            self.system_message is not None
            and role != OpenAIBackendRole.SYSTEM
        ):
            messages.append(
                self.system_message.to_openai_message(
                    OpenAIBackendRole.SYSTEM
                )
            )
        messages.append(message.to_openai_message(role))
        try:
            tokens = self.context_settings.token_counter.count_tokens_from_messages(
                messages
            )
        except Exception:
            return False
        return tokens <= self.context_settings.context_token_limit

    def _ensure_system_message_in_memory(self) -> None:
        records = self.memory.retrieve()
        if any(
            record.memory_record.role_at_backend == OpenAIBackendRole.SYSTEM
            for record in records
        ):
            return
        if self.system_message is None:
            return
        self.memory.write_record(
            MemoryRecord(
                message=self.system_message,
                role_at_backend=OpenAIBackendRole.SYSTEM,
                timestamp=time.time_ns() / 1_000_000_000,
                agent_id=self.agent_id,
            )
        )
