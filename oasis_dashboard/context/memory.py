from __future__ import annotations

from camel.memories import ChatHistoryMemory, ScoreBasedContextCreator
from camel.types import OpenAIBackendRole
from camel.utils import BaseTokenCounter


class ContextChatHistoryMemory(ChatHistoryMemory):
    def clean_tool_calls(self) -> None:
        record_dicts = self._chat_history_block.storage.load()
        if not record_dicts:
            return

        cleaned_records = []
        for record in record_dicts:
            role = record.get("role_at_backend")
            message = record.get("message", {})
            message_class = message.get("__class__")
            message_meta = message.get("meta_dict") or {}

            if role in (
                OpenAIBackendRole.FUNCTION.value,
                OpenAIBackendRole.TOOL.value,
            ):
                continue

            if role == OpenAIBackendRole.ASSISTANT.value and (
                "tool_calls" in message_meta
                or message_class == "FunctionCallingMessage"
            ):
                continue

            cleaned_records.append(record)

        self._chat_history_block.storage.clear()
        self._chat_history_block.storage.save(cleaned_records)


def build_chat_history_memory(
    *,
    token_counter: BaseTokenCounter,
    context_token_limit: int,
    agent_id: str,
    window_size: int | None = None,
) -> ContextChatHistoryMemory:
    return ContextChatHistoryMemory(
        ScoreBasedContextCreator(token_counter, context_token_limit),
        window_size=window_size,
        agent_id=agent_id,
    )
