from __future__ import annotations

import copy
import inspect
import re
import time
from types import MethodType
from typing import Any, Mapping, Optional, Union

from camel.memories import MemoryRecord
from camel.messages import BaseMessage, FunctionCallingMessage
from camel.models import BaseModelBackend, ModelManager
from camel.responses import ChatAgentResponse
from camel.toolkits import FunctionTool
from camel.types import OpenAIBackendRole
from oasis import AgentGraph, SocialAgent
from oasis.social_platform import Channel
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType

from .action_evidence import ActionEvidenceBuilder
from .action_significance import normalize_execution_status
from .budget_recovery import BudgetRecoveryController
from .config import ActionV1RuntimeSettings
from .consolidator import Consolidator
from .environment import ActionV1SocialEnvironment
from .episodic_memory import ActionEpisode, HeartbeatRange, StepRecord, StepRecordKind, StepSegment, build_platform_memory_adapter
from .memory import build_chat_history_memory
from .observation_policy import DefaultObservationPolicy
from .observation_semantics import build_prompt_visible_snapshot
from .prompt_assembler import PromptAssemblyResult, PromptAssembler
from .recall_planner import RecallPlanner, RecallRuntimeState
from .retrieval_policy import RetrievalPolicy
from .runtime_failures import ActionV1RuntimeFailure, ContextBudgetExhaustedError, normalize_model_error
from .working_memory import CompressedWorkingMemory, MemoryState, RecentWorkingMemory


THINK_BLOCK_RE = re.compile(r"<think>.*?(?:</think>|$)\s*", re.DOTALL)
STEP_ID_EXTRA_KEY = "oasis_step_id"
STEP_KIND_EXTRA_KEY = "oasis_step_kind"
ACTION_V1_OUTCOME_ALIGNMENT_NOTE = (
    "Outcome reporting rule: in the final textual explanation for this step, "
    "describe only the action(s) you actually executed via tool calls in this "
    "step. Do not describe unexecuted alternatives. Use the correct object "
    "type (post, comment, user, or group), and do not claim you performed an "
    "action that is not available in the current tool list."
)


def _record_first_output_message(self, output_messages):
    if not output_messages:
        return
    self.record_message(output_messages[0])


def _augment_action_v1_system_message(system_message: BaseMessage) -> BaseMessage:
    content = str(getattr(system_message, "content", "") or "").strip()
    if ACTION_V1_OUTCOME_ALIGNMENT_NOTE in content:
        return system_message
    augmented = (
        f"{content}\n\n{ACTION_V1_OUTCOME_ALIGNMENT_NOTE}"
        if content
        else ACTION_V1_OUTCOME_ALIGNMENT_NOTE
    )
    return system_message.create_new_instance(augmented)


class _BoundedChatHistoryAgentMixin:
    _bounded_token_counter: Any
    _bounded_context_token_limit: int
    _sanitize_assistant_think_blocks: bool

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

        message = self._sanitize_message_for_memory(message, role)
        if not self._message_fits_context_limit(message, role):
            delegated_kwargs = {}
            for key in bound.arguments:
                if key == "message":
                    delegated_kwargs[key] = message
                elif key == "role":
                    delegated_kwargs[key] = role
                elif key == "timestamp":
                    delegated_kwargs[key] = timestamp
            return parent_method(**delegated_kwargs)

        self.memory.write_record(
            MemoryRecord(
                message=message,
                role_at_backend=role,
                extra_info=self._build_memory_extra_info(role),
                timestamp=timestamp if timestamp is not None else time.time_ns() / 1_000_000_000,
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
        if self.system_message is not None and role != OpenAIBackendRole.SYSTEM:
            messages.append(self.system_message.to_openai_message(OpenAIBackendRole.SYSTEM))
        messages.append(message.to_openai_message(role))
        try:
            tokens = self._bounded_token_counter.count_tokens_from_messages(messages)
        except Exception:
            return False
        return tokens <= self._bounded_context_token_limit

    def _sanitize_message_for_memory(
        self,
        message: BaseMessage,
        role: OpenAIBackendRole,
    ) -> BaseMessage:
        if not getattr(self, "_sanitize_assistant_think_blocks", True):
            return message
        if role != OpenAIBackendRole.ASSISTANT:
            return message
        if not isinstance(message.content, str) or "<think>" not in message.content:
            return message

        sanitized_content = THINK_BLOCK_RE.sub("", message.content).strip()
        if sanitized_content == message.content:
            return message
        return message.create_new_instance(sanitized_content)

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

    def _build_memory_extra_info(self, role: OpenAIBackendRole) -> dict[str, str]:
        del role
        return {}


class ContextSocialAgent(_BoundedChatHistoryAgentMixin, SocialAgent):
    def __init__(
        self,
        agent_id: int,
        user_info: UserInfo,
        user_info_template=None,
        channel: Channel | None = None,
        model: Optional[Union[BaseModelBackend, list[BaseModelBackend], ModelManager]] = None,
        agent_graph=None,
        available_actions: list[ActionType] | None = None,
        tools: Optional[list[Union[FunctionTool, Any]]] = None,
        max_iteration: int = 1,
        interview_record: bool = False,
        context_settings: ActionV1RuntimeSettings | None = None,
    ):
        if context_settings is None:
            raise ValueError("context_settings is required for ContextSocialAgent.")

        context_settings.system_message = _augment_action_v1_system_message(
            context_settings.system_message
        )
        self.context_settings = context_settings
        self.token_counter = context_settings.token_counter
        self.context_token_limit = context_settings.context_token_limit
        self.memory_window_size = context_settings.memory_window_size
        self.token_counter_mode = context_settings.token_counter_mode
        self.context_window_source = context_settings.context_window_source
        self._bounded_token_counter = context_settings.token_counter
        self._bounded_context_token_limit = context_settings.context_token_limit
        self._sanitize_assistant_think_blocks = True
        platform_name = str(getattr(user_info, "recsys_type", "unknown"))
        self._memory_state = MemoryState(
            recent=RecentWorkingMemory(),
            compressed=CompressedWorkingMemory(),
        )
        self._heartbeat_ranges = self._memory_state.compressed.heartbeat_ranges
        self._persisted_action_episode_ids: set[tuple[int, int]] = set()
        self._persisted_episode_step_ids: set[int] = set()
        self._last_step_action_episodes: list[ActionEpisode] = []
        self._last_persistable_action_step_id: int | None = None
        self._last_internal_trace: dict[str, Any] = {}
        self._last_runtime_failure_trace: dict[str, Any] = {}
        self._last_action_v1_prompt_tokens: int = 0
        self._last_prompt_assembly_result: PromptAssemblyResult | None = None
        self._longterm_store = (
            context_settings.longterm_sidecar.store
            if context_settings.longterm_sidecar.enabled
            else None
        )
        self._episodic_adapter = build_platform_memory_adapter(platform_name)
        self._observation_policy = DefaultObservationPolicy()
        self._action_evidence_builder = ActionEvidenceBuilder()
        self._retrieval_policy = RetrievalPolicy()
        self._recall_planner = RecallPlanner(
            runtime_settings=context_settings,
            retrieval_policy=self._retrieval_policy,
        )
        self._recall_runtime_state = RecallRuntimeState()
        self._prompt_assembler = PromptAssembler(
            runtime_settings=context_settings,
            retrieval_policy=self._retrieval_policy,
        )
        self._budget_recovery_controller = BudgetRecoveryController(
            runtime_settings=context_settings
        )
        self._consolidator = Consolidator(runtime_settings=context_settings)
        self._step_counter = 0
        self._active_step_id: int | None = None
        self._last_longterm_query_source: str = ""
        self._last_longterm_query_text: str = ""
        self._last_longterm_recalled_count: int = 0
        self._last_longterm_injected_count: int = 0
        self._last_longterm_reason_trace: str = ""
        self._last_longterm_recalled_step_ids: list[int] = []
        self._last_longterm_injected_step_ids: list[int] = []
        self._last_longterm_retrieval_step_id: int | None = None

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
        self._original_system_message = context_settings.system_message
        self._system_message = context_settings.system_message

        original_action = self.env.action
        actionable_tool_names = {
            tool.func.__name__
            for tool in (self.action_tools or [])
            if hasattr(tool, "func")
        }
        self.env = ActionV1SocialEnvironment(
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
        self._record_final_output = MethodType(_record_first_output_message, self)
        self._ensure_system_message_in_memory()
        self.prune_tool_calls_from_memory = True

    async def perform_action_by_llm(self):
        return await self._perform_action_by_llm_action_v1()

    async def _perform_action_by_llm_action_v1(self):
        observation_prompt = await self.env.to_text_prompt()
        step_timestamp = time.time()
        step_id = self._step_counter + 1
        base_artifact = copy.deepcopy(getattr(self.env, "last_observation_artifact", None))
        raw_payload = copy.deepcopy(getattr(self.env, "last_raw_observation_payload", None) or {})
        if base_artifact is None:
            base_artifact = getattr(self.env, "last_observation_artifact", None)
            if base_artifact is None:
                raise RuntimeError("missing observation artifact for action_v1 step")

        self._reset_longterm_step_trace_state()
        recovery_state = self._budget_recovery_controller.initial_state()
        self._active_step_id = step_id
        try:
            while True:
                artifact = self._budget_recovery_controller.observation_artifact_for_state(
                    base_artifact=base_artifact,
                    raw_payload=raw_payload,
                    current_agent_id=self.agent_id,
                    state=recovery_state,
                )
                self.env.publish_observation_artifact(artifact, raw_payload=raw_payload)
                perception = self._observation_policy.build_perception_envelope(
                    prompt_visible_snapshot=artifact.prompt_visible_snapshot,
                    observation_prompt=artifact.observation_prompt,
                )
                derived_memory_state = self._budget_recovery_controller.derived_memory_state(
                    memory_state=self._memory_state,
                    state=recovery_state,
                )
                recall_preparation = self._recall_planner.prepare(
                    agent_id=self.agent_id,
                    topic=perception.topic,
                    semantic_anchors=perception.semantic_anchors,
                    entities=perception.entities,
                    snapshot=perception.snapshot,
                    memory_state=derived_memory_state,
                    longterm_store=self._longterm_store,
                    next_step_id=step_id,
                    runtime_state=self._recall_runtime_state,
                )
                self._last_internal_trace = {
                    "last_recall_gate": bool(recall_preparation.gate_decision),
                    "last_recall_gate_reason_flags": dict(
                        recall_preparation.gate_reason_flags
                    ),
                    "last_recall_query_source": str(recall_preparation.query_source or ""),
                    "last_recall_query_text": str(recall_preparation.query_text or ""),
                    "last_recall_candidate_count": int(recall_preparation.recalled_count),
                }
                assembly = self._prompt_assembler.assemble(
                    system_message=self.system_message,
                    current_observation_prompt=artifact.observation_prompt,
                    memory_state=derived_memory_state,
                    recall_candidates=self._budget_recovery_controller.derive_recall_candidates(
                        recall_candidates=recall_preparation.candidates,
                        state=recovery_state,
                    ),
                    effective_prompt_budget=self._budget_recovery_controller.effective_prompt_budget(
                        state=recovery_state
                    ),
                )
                self._last_action_v1_prompt_tokens = assembly.total_tokens
                self._last_prompt_assembly_result = assembly
                self._last_internal_trace.update(
                    {
                        "last_prompt_budget_status": assembly.budget_status,
                        "last_prompt_failure_reason": assembly.assembly_failure_reason,
                        "last_selected_recent_step_ids": list(
                            assembly.selected_recent_step_ids
                        ),
                        "last_selected_compressed_keys": list(
                            assembly.selected_compressed_keys
                        ),
                        "last_selected_recall_step_ids": list(
                            assembly.selected_recall_step_ids
                        ),
                    }
                )
                if assembly.budget_status != "ok":
                    next_state = self._budget_recovery_controller.next_for_local_over_budget(
                        state=recovery_state
                    )
                    if next_state is None:
                        raise ContextBudgetExhaustedError(
                            reason=assembly.assembly_failure_reason
                            or "base_prompt_exceeds_effective_prompt_budget",
                            step_id=step_id,
                            details=self._build_runtime_failure_trace(
                                failure_stage="pre_decision_prompt_assembly_failure",
                                failure_category="context_budget_exhausted",
                                recovery_state=recovery_state,
                                assembly=assembly,
                            ),
                        )
                    recovery_state = next_state
                    continue

                try:
                    response = await self._astep_with_assembled_messages(assembly)
                except Exception as exc:
                    normalized = normalize_model_error(
                        exc,
                        backend_family=self.context_settings.model_backend_family,
                        provider_preset=self.context_settings.provider_runtime_preset,
                    )
                    if normalized.category == "context_overflow":
                        next_state = self._budget_recovery_controller.next_for_provider_overflow(
                            state=recovery_state
                        )
                        if next_state is None:
                            raise ContextBudgetExhaustedError(
                                reason=normalized.message,
                                step_id=step_id,
                                details=self._build_runtime_failure_trace(
                                    failure_stage="pre_decision_model_failure",
                                    failure_category="context_budget_exhausted",
                                    recovery_state=recovery_state,
                                    assembly=assembly,
                                ),
                            ) from exc
                        recovery_state = next_state
                        continue
                    raise ActionV1RuntimeFailure(
                        category=normalized.category,
                        reason=normalized.message,
                        step_id=step_id,
                        details=self._build_runtime_failure_trace(
                            failure_stage="pre_decision_model_failure",
                            failure_category=normalized.category,
                            recovery_state=recovery_state,
                            assembly=assembly,
                        ),
                    ) from exc

                if isinstance(response, ChatAgentResponse):
                    self._recall_planner.commit_selection(
                        runtime_state=self._recall_runtime_state,
                        preparation=recall_preparation,
                        selected_items=assembly.selected_recall_items,
                        step_id=step_id,
                    )
                    self._sync_legacy_longterm_fields_from_recall_state()
                    self._record_step_memory_contract(
                        step_id=step_id,
                        user_message=assembly.current_observation_message,
                        response=response,
                        timestamp=step_timestamp,
                    )
                return response
        finally:
            self._active_step_id = None

    def _build_runtime_failure_trace(
        self,
        *,
        failure_stage: str,
        failure_category: str = "",
        recovery_state,
        assembly: PromptAssemblyResult | None,
    ) -> dict[str, Any]:
        details = {
            "category": failure_category,
            "failure_stage": failure_stage,
            "backend_family": self.context_settings.model_backend_family,
            "pressure_level": recovery_state.pressure_level,
            "attempt_index": recovery_state.attempt_index,
            "effective_prompt_budget": self._budget_recovery_controller.effective_prompt_budget(
                state=recovery_state
            ),
            "selected_recent_step_ids": list(assembly.selected_recent_step_ids) if assembly else [],
            "selected_compressed_keys": list(assembly.selected_compressed_keys) if assembly else [],
            "selected_recall_step_ids": list(assembly.selected_recall_step_ids) if assembly else [],
            "selected_recall_count": int(assembly.selected_recall_count) if assembly else 0,
            "budget_status": assembly.budget_status if assembly else "",
            "assembly_failure_reason": assembly.assembly_failure_reason if assembly else "",
        }
        self._last_runtime_failure_trace = dict(details)
        return details

    def _current_prompt_visible_snapshot(self) -> dict[str, Any]:
        observation_snapshot = copy.deepcopy(
            getattr(self.env, "last_prompt_visible_snapshot", None) or {}
        )
        if observation_snapshot:
            return observation_snapshot
        return build_prompt_visible_snapshot(
            posts_payload=copy.deepcopy(
                (getattr(self.env, "last_visible_observation_payload", None) or {}).get(
                    "posts", {}
                )
            ),
            groups_payload=copy.deepcopy(
                (getattr(self.env, "last_visible_observation_payload", None) or {}).get(
                    "groups", {}
                )
            ),
            current_agent_id=self.agent_id,
        )

    def _sync_legacy_longterm_fields_from_recall_state(self) -> None:
        state = self._recall_runtime_state
        self._last_longterm_query_source = state.last_successful_query_source
        self._last_longterm_query_text = state.last_successful_query_text
        self._last_longterm_recalled_count = state.last_recalled_count
        self._last_longterm_injected_count = state.last_injected_count
        self._last_longterm_reason_trace = state.last_reason_trace
        self._last_longterm_recalled_step_ids = list(state.last_recalled_step_ids)
        self._last_longterm_injected_step_ids = list(state.last_injected_step_ids)
        self._last_longterm_retrieval_step_id = state.last_successful_step_id

    def _reset_longterm_step_trace_state(self) -> None:
        self._recall_runtime_state.last_recalled_count = 0
        self._recall_runtime_state.last_recalled_step_ids = []
        self._recall_runtime_state.last_injected_count = 0
        self._recall_runtime_state.last_injected_step_ids = []
        self._recall_runtime_state.last_injected_action_keys = []
        self._recall_runtime_state.last_reason_trace = ""
        self._last_runtime_failure_trace = {}
        self._last_step_action_episodes = []
        self._last_internal_trace = {}
        self._sync_legacy_longterm_fields_from_recall_state()

    def _record_step_memory_contract(
        self,
        *,
        step_id: int,
        user_message: BaseMessage,
        response: ChatAgentResponse,
        timestamp: float,
    ) -> None:
        self._step_counter = max(self._step_counter, step_id)
        segment = StepSegment(
            agent_id=str(self.agent_id),
            step_id=step_id,
            timestamp=timestamp,
            platform=str(getattr(self.user_info, "recsys_type", "unknown")),
            records=self._build_step_records(user_message=user_message, response=response),
        )
        action_episodes = self._episodic_adapter.build_action_episodes(segment)
        persistable_action_episodes, non_persistable_action_episodes = (
            self._partition_persistable_action_episodes(action_episodes)
        )
        self._assign_idle_step_gaps(
            persistable_action_episodes,
            non_persistable_action_episodes=non_persistable_action_episodes,
        )
        self._last_step_action_episodes = list(action_episodes)
        self._persist_action_episodes(persistable_action_episodes)
        self._consolidator.maintain(
            memory_state=self._memory_state,
            new_segment=segment,
            action_episodes=action_episodes,
            adapter=self._episodic_adapter,
        )

    def _build_step_records(
        self,
        *,
        user_message: BaseMessage,
        response: ChatAgentResponse,
    ) -> list[StepRecord]:
        records: list[StepRecord] = []
        prompt_visible_snapshot = copy.deepcopy(
            getattr(self.env, "last_prompt_visible_snapshot", None) or {}
        )
        if not prompt_visible_snapshot:
            prompt_visible_snapshot = self._current_prompt_visible_snapshot()
        perception = self._observation_policy.build_perception_envelope(
            prompt_visible_snapshot=prompt_visible_snapshot,
            observation_prompt=user_message.content,
        )
        records.append(
            StepRecord(
                role="user",
                kind=StepRecordKind.PERCEPTION,
                content=user_message.content,
                metadata={
                    "entities": perception.entities,
                    "topic": perception.topic,
                    "topics": perception.topics,
                    "semantic_anchors": perception.semantic_anchors,
                    "snapshot": perception.snapshot,
                    "prompt_visible_snapshot": prompt_visible_snapshot,
                    "observation_prompt": getattr(self.env, "last_observation_prompt", ""),
                    "used_recall_count": self._last_longterm_injected_count,
                    "used_recall_step_ids": self._last_longterm_injected_step_ids,
                    "reason_trace": self._last_longterm_reason_trace,
                },
            )
        )

        for tool_call in response.info.get("tool_calls", []) or []:
            tool_name = str(getattr(tool_call, "tool_name", "") or "")
            tool_args = getattr(tool_call, "args", {}) or {}
            tool_result = getattr(tool_call, "result", None)
            tool_call_id = str(getattr(tool_call, "tool_call_id", "") or "")
            action_evidence = self._action_evidence_builder.build(
                prompt_visible_snapshot=prompt_visible_snapshot,
                action_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
            )
            action_fact = self._episodic_adapter.format_action_fact(
                tool_name=tool_name,
                tool_args=tool_args,
            )
            records.append(
                StepRecord(
                    role="assistant",
                    kind=StepRecordKind.DECISION,
                    content=action_fact,
                    metadata={
                        "action": action_fact,
                        "action_name": tool_name,
                        "tool_call_id": tool_call_id,
                        "args": copy.deepcopy(tool_args),
                        "action_evidence": action_evidence.to_metadata_dict(),
                    },
                )
            )
            records.append(
                StepRecord(
                    role="tool",
                    kind=StepRecordKind.ACTION_RESULT,
                    content=str(tool_result or ""),
                    metadata={
                        "action": action_fact,
                        "action_name": tool_name,
                        "tool_call_id": tool_call_id,
                        "result": copy.deepcopy(tool_result),
                        "state_changes": self._episodic_adapter.derive_state_changes(
                            tool_name=tool_name,
                            tool_args=tool_args,
                            tool_result=tool_result,
                        ),
                        "action_evidence": action_evidence.to_metadata_dict(),
                    },
                )
            )

        for message in response.msgs:
            if not isinstance(message.content, str):
                continue
            sanitized_content = THINK_BLOCK_RE.sub("", message.content).strip()
            if sanitized_content != message.content:
                records.append(
                    StepRecord(
                        role="assistant",
                        kind=StepRecordKind.REASONING_NOISE,
                        content="[assistant_think_block_removed]",
                    )
                )
            if sanitized_content:
                records.append(
                    StepRecord(
                        role="assistant",
                        kind=StepRecordKind.FINAL_OUTCOME,
                        content=sanitized_content,
                    )
                )
        return records

    def _build_memory_extra_info(self, role: OpenAIBackendRole) -> dict[str, str]:
        if self._active_step_id is None:
            return {}
        if role == OpenAIBackendRole.USER:
            kind = StepRecordKind.PERCEPTION.value
        elif role == OpenAIBackendRole.ASSISTANT:
            kind = StepRecordKind.FINAL_OUTCOME.value
        elif role in (OpenAIBackendRole.FUNCTION, OpenAIBackendRole.TOOL):
            kind = StepRecordKind.ACTION_RESULT.value
        else:
            kind = "other"
        return {
            STEP_ID_EXTRA_KEY: str(self._active_step_id),
            STEP_KIND_EXTRA_KEY: kind,
        }

    def _persist_action_episodes(self, episodes: list[ActionEpisode]) -> list[ActionEpisode]:
        if self._longterm_store is None or not episodes:
            return []
        pending = [
            episode
            for episode in episodes
            if (episode.step_id, episode.action_index) not in self._persisted_action_episode_ids
        ]
        if not pending:
            return []
        payloads = [episode.to_payload() for episode in pending]
        self._longterm_store.write_episodes(payloads)
        self._persisted_action_episode_ids.update(
            (episode.step_id, episode.action_index) for episode in pending
        )
        self._persisted_episode_step_ids.update(episode.step_id for episode in pending)
        return pending

    def _partition_persistable_action_episodes(
        self,
        episodes: list[ActionEpisode],
    ) -> tuple[list[ActionEpisode], list[ActionEpisode]]:
        persistable: list[ActionEpisode] = []
        non_persistable: list[ActionEpisode] = []
        for episode in episodes:
            if (
                normalize_execution_status(episode.execution_status) == "hallucinated"
                or episode.target_resolution_status == "invalid_target"
            ):
                non_persistable.append(episode)
                continue
            persistable.append(episode)
        return persistable, non_persistable

    def _assign_idle_step_gaps(
        self,
        episodes: list[ActionEpisode],
        *,
        non_persistable_action_episodes: list[ActionEpisode] | None = None,
    ) -> None:
        for episode in non_persistable_action_episodes or []:
            episode.idle_step_gap = 0
        if not episodes:
            return
        previous_step_id = self._last_persistable_action_step_id
        for index, episode in enumerate(episodes):
            if index == 0 and previous_step_id is not None:
                episode.idle_step_gap = max(0, episode.step_id - previous_step_id - 1)
            else:
                episode.idle_step_gap = 0
        self._last_persistable_action_step_id = episodes[0].step_id

    async def _astep_with_assembled_messages(
        self,
        assembly: PromptAssemblyResult,
    ) -> ChatAgentResponse:
        disable_tools = self._is_called_from_registered_toolkit()
        tool_call_records: list[Any] = []
        external_tool_call_requests: list[Any] | None = None
        accumulated_context_tokens = 0
        step_token_usage = self._create_token_usage_tracker()
        iteration_count = 0
        prev_num_openai_messages = 0
        runtime_messages = list(assembly.openai_messages)

        while True:
            num_tokens = self.context_settings.token_counter.count_tokens_from_messages(
                runtime_messages
            )
            accumulated_context_tokens += num_tokens
            response = await self._aget_model_response(
                runtime_messages,
                num_tokens=num_tokens,
                current_iteration=iteration_count,
                response_format=None,
                tool_schemas=[] if disable_tools else self._get_full_tool_schemas(),
                prev_num_openai_messages=prev_num_openai_messages,
            )
            prev_num_openai_messages = len(runtime_messages)
            iteration_count += 1
            self._update_token_usage_tracker(step_token_usage, response.usage_dict)

            if self.stop_event and self.stop_event.is_set():
                return self._step_terminate(
                    accumulated_context_tokens,
                    tool_call_records,
                    "termination_triggered",
                )

            if tool_call_requests := response.tool_call_requests:
                tool_execution_failed = False
                for tool_call_request in tool_call_requests:
                    if tool_call_request.tool_name in self._external_tool_schemas:
                        if external_tool_call_requests is None:
                            external_tool_call_requests = []
                        external_tool_call_requests.append(tool_call_request)
                        continue
                    try:
                        tool_record = await self._aexecute_tool(tool_call_request)
                    except Exception as exc:
                        failed_result = self._build_failed_tool_result(
                            tool_name=str(getattr(tool_call_request, "tool_name", "") or ""),
                            tool_args=getattr(tool_call_request, "args", {}) or {},
                            exc=exc,
                        )
                        tool_record = self._record_tool_calling(
                            func_name=str(getattr(tool_call_request, "tool_name", "") or ""),
                            args=getattr(tool_call_request, "args", {}) or {},
                            result=failed_result,
                            tool_call_id=str(getattr(tool_call_request, "tool_call_id", "") or ""),
                        )
                        tool_execution_failed = True
                    tool_call_records.append(tool_record)
                    if tool_execution_failed:
                        break
                    runtime_messages.extend(self._tool_record_to_openai_messages(tool_record))

                if external_tool_call_requests or tool_execution_failed:
                    break
                if self.max_iteration is not None and iteration_count >= self.max_iteration:
                    break
                continue
            break

        if self.prune_tool_calls_from_memory and tool_call_records:
            self.memory.clean_tool_calls()

        return self._convert_to_chatagent_response(
            response,
            tool_call_records,
            accumulated_context_tokens,
            external_tool_call_requests,
            step_token_usage["prompt_tokens"],
            step_token_usage["completion_tokens"],
            step_token_usage["total_tokens"],
        )

    def _tool_record_to_openai_messages(self, tool_record: Any) -> list[dict[str, Any]]:
        tool_call_id = str(getattr(tool_record, "tool_call_id", "") or "")
        assist_msg = FunctionCallingMessage(
            role_name=self.role_name,
            role_type=self.role_type,
            meta_dict=None,
            content="",
            func_name=getattr(tool_record, "tool_name", ""),
            args=getattr(tool_record, "args", {}) or {},
            tool_call_id=tool_call_id,
        )
        func_msg = FunctionCallingMessage(
            role_name=self.role_name,
            role_type=self.role_type,
            meta_dict=None,
            content="",
            func_name=getattr(tool_record, "tool_name", ""),
            result=getattr(tool_record, "result", None),
            tool_call_id=tool_call_id,
        )
        return [
            assist_msg.to_openai_message(OpenAIBackendRole.ASSISTANT),
            func_msg.to_openai_message(OpenAIBackendRole.FUNCTION),
        ]

    def _build_failed_tool_result(
        self,
        *,
        tool_name: str,
        tool_args: Mapping[str, Any],
        exc: Exception,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "error": str(exc or exc.__class__.__name__),
            "exception_type": exc.__class__.__name__,
            "failure_stage": "post_decision_execution_failure",
            "tool_name": tool_name,
            "tool_args": copy.deepcopy(dict(tool_args)),
        }

    @property
    def step_segments(self) -> list[StepSegment]:
        return list(self._memory_state.recent.segments)

    @property
    def action_episode_records(self) -> list[ActionEpisode]:
        return list(self._last_step_action_episodes)

    @property
    def heartbeat_ranges(self) -> list[HeartbeatRange]:
        return list(self._memory_state.compressed.heartbeat_ranges)

    def memory_debug_snapshot(self) -> dict[str, Any]:
        recent_step_ids = [segment.step_id for segment in self._memory_state.recent.segments]
        compressed_step_ids: set[int] = set()
        for block in self._memory_state.compressed.action_blocks:
            compressed_step_ids.update(block.covered_step_ids)
        for heartbeat in self._memory_state.compressed.heartbeat_ranges:
            compressed_step_ids.update(range(heartbeat.start_step, heartbeat.end_step + 1))

        render_stats = dict(getattr(self.env, "last_render_stats", {}) or {})
        failure_trace = dict(self._last_runtime_failure_trace or {})
        assembly = self._last_prompt_assembly_result
        internal_trace = dict(self._last_internal_trace or {})

        return {
            "memory_runtime": "action_v1",
            "memory_supported": True,
            "recent_retained_step_count": len(recent_step_ids),
            "recent_retained_step_ids": recent_step_ids,
            "compressed_action_block_count": len(self._memory_state.compressed.action_blocks),
            "compressed_heartbeat_count": len(self._memory_state.compressed.heartbeat_ranges),
            "compressed_retained_step_count": len(compressed_step_ids),
            "total_retained_step_count": len(set(recent_step_ids) | compressed_step_ids),
            "last_observation_stage": str(render_stats.get("final_shaping_stage", "") or ""),
            "last_observation_prompt_tokens": int(
                render_stats.get("observation_prompt_tokens", 0) or 0
            ),
            "last_prompt_tokens": int(self._last_action_v1_prompt_tokens or 0),
            "last_recall_gate": (
                bool(internal_trace.get("last_recall_gate"))
                if "last_recall_gate" in internal_trace
                else None
            ),
            "last_recall_gate_reason_flags": dict(
                internal_trace.get("last_recall_gate_reason_flags", {}) or {}
            ),
            "last_recall_query_source": str(
                internal_trace.get("last_recall_query_source", "") or ""
            ),
            "last_recall_query_text": str(
                internal_trace.get("last_recall_query_text", "") or ""
            ),
            "last_recalled_count": int(self._last_longterm_recalled_count or 0),
            "last_injected_count": int(self._last_longterm_injected_count or 0),
            "last_recalled_step_ids": list(self._last_longterm_recalled_step_ids),
            "last_injected_step_ids": list(self._last_longterm_injected_step_ids),
            "last_recall_reason_trace": str(self._last_longterm_reason_trace or ""),
            "last_runtime_failure_category": str(
                failure_trace.get("category", "") or ""
            ),
            "last_runtime_failure_stage": str(
                failure_trace.get("failure_stage", "") or ""
            ),
            "last_prompt_budget_status": (
                str(assembly.budget_status or "") if assembly is not None else ""
            ),
            "last_selected_recent_step_ids": list(
                internal_trace.get("last_selected_recent_step_ids", []) or []
            ),
            "last_selected_compressed_keys": list(
                internal_trace.get("last_selected_compressed_keys", []) or []
            ),
            "last_selected_recall_step_ids": list(
                internal_trace.get("last_selected_recall_step_ids", []) or []
            ),
        }


def build_upstream_social_agent(
    *,
    agent_id: int,
    user_info: UserInfo,
    agent_graph: AgentGraph,
    model: Any,
    available_actions: list[ActionType],
) -> SocialAgent:
    return SocialAgent(
        agent_id=agent_id,
        user_info=user_info,
        agent_graph=agent_graph,
        model=model,
        available_actions=available_actions,
    )


def build_action_v1_social_agent(
    *,
    agent_id: int,
    user_info: UserInfo,
    agent_graph: AgentGraph,
    model: Any,
    available_actions: list[ActionType],
    context_settings: ActionV1RuntimeSettings,
) -> ContextSocialAgent:
    return ContextSocialAgent(
        agent_id=agent_id,
        user_info=user_info,
        agent_graph=agent_graph,
        model=model,
        available_actions=available_actions,
        context_settings=context_settings,
    )
