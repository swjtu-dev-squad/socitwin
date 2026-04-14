from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from .config import ActionV1RuntimeSettings
from .memory_rendering import (
    CompressedNoteView,
    RecentTurnView,
    build_action_block_note_view,
    build_heartbeat_note_view,
    build_recent_turn_view,
)
from .retrieval_policy import RetrievalPolicy
from .working_memory import (
    MemoryState,
    RecallOverlapFilterDecision,
    RecallOverlapState,
    build_recall_overlap_state_from_views,
    explain_recall_candidates_by_overlap,
    filter_recall_candidates_by_overlap,
)


@dataclass(slots=True)
class PromptAssemblyResult:
    openai_messages: list[dict[str, Any]]
    current_observation_message: BaseMessage
    total_tokens: int
    selected_recent_step_ids: list[int] = field(default_factory=list)
    selected_compressed_keys: list[str] = field(default_factory=list)
    selected_recall_action_keys: list[tuple[int, int]] = field(default_factory=list)
    selected_recall_step_ids: list[int] = field(default_factory=list)
    selected_recall_count: int = 0
    selected_recall_items: list[dict[str, Any]] = field(default_factory=list)
    recall_candidate_count: int = 0
    recall_overlap_filtered_count: int = 0
    recall_overlap_filtered_step_ids: list[int] = field(default_factory=list)
    recall_overlap_filter_reasons: list[dict[str, Any]] = field(default_factory=list)
    recall_selection_stop_reason: str = ""
    recall_selection_stop_step_id: int | None = None
    recall_selection_stop_tokens: int | None = None
    recall_selection_budget: int | None = None
    budget_status: str = "ok"
    assembly_failure_reason: str = ""


class PromptAssembler:
    def __init__(
        self,
        runtime_settings: ActionV1RuntimeSettings,
        retrieval_policy: RetrievalPolicy,
    ) -> None:
        self.runtime_settings = runtime_settings
        self.retrieval_policy = retrieval_policy

    def assemble(
        self,
        *,
        system_message: BaseMessage,
        current_observation_prompt: str,
        memory_state: MemoryState,
        recall_candidates: list[Mapping[str, Any]],
        effective_prompt_budget: int | None = None,
    ) -> PromptAssemblyResult:
        current_observation_message = BaseMessage.make_user_message(
            role_name="User",
            content=self.runtime_settings.observation_wrapper.format(
                env_prompt=current_observation_prompt
            ),
        )
        selected_recent: list[RecentTurnView] = []
        selected_compressed: list[CompressedNoteView] = []
        selected_recall: list[Mapping[str, Any]] = []

        prompt_budget = (
            effective_prompt_budget
            if effective_prompt_budget is not None
            else self.runtime_settings.effective_prompt_budget
        )
        recent_budget = int(
            prompt_budget * self.runtime_settings.working_memory_budget.recent_budget_ratio
        )
        compressed_budget = int(
            prompt_budget
            * self.runtime_settings.working_memory_budget.compressed_budget_ratio
        )
        recall_budget = int(
            prompt_budget * self.runtime_settings.working_memory_budget.recall_budget_ratio
        )

        base_messages = self._materialize(
            system_message=system_message,
            current_observation_message=current_observation_message,
            compressed_notes=[],
            recent_turns=[],
            recall_note="",
        )
        if self._count_tokens(base_messages) > prompt_budget:
            return PromptAssemblyResult(
                openai_messages=base_messages,
                current_observation_message=current_observation_message,
                total_tokens=self._count_tokens(base_messages),
                recall_candidate_count=len(recall_candidates),
                recall_selection_stop_reason="base_prompt_over_budget",
                budget_status="base_prompt_over_budget",
                assembly_failure_reason="base_prompt_exceeds_effective_prompt_budget",
            )

        recent_views = self._build_recent_turn_views(memory_state.recent.segments)
        compressed_views = self._build_compressed_note_views(
            action_blocks=memory_state.compressed.action_blocks,
            heartbeat_ranges=memory_state.compressed.heartbeat_ranges,
        )
        recall_note_title = self.runtime_settings.summary_preset.recall_note_title

        recent_tokens = 0
        for view in reversed(recent_views):
            candidate_tokens = self._count_tokens(self._recent_turn_messages(view))
            if recent_tokens + candidate_tokens > recent_budget:
                continue
            candidate_recent = [view, *selected_recent]
            candidate_messages = self._materialize(
                system_message=system_message,
                current_observation_message=current_observation_message,
                compressed_notes=selected_compressed,
                recent_turns=candidate_recent,
                recall_note="",
            )
            if self._count_tokens(candidate_messages) > prompt_budget:
                continue
            selected_recent = candidate_recent
            recent_tokens += candidate_tokens

        compressed_tokens = 0
        for note in reversed(compressed_views):
            candidate_tokens = self._count_tokens([self._assistant_message(note.text)])
            if compressed_tokens + candidate_tokens > compressed_budget:
                continue
            candidate_compressed = [note, *selected_compressed]
            candidate_messages = self._materialize(
                system_message=system_message,
                current_observation_message=current_observation_message,
                compressed_notes=candidate_compressed,
                recent_turns=selected_recent,
                recall_note="",
            )
            if self._count_tokens(candidate_messages) > prompt_budget:
                continue
            selected_compressed = candidate_compressed
            compressed_tokens += candidate_tokens

        overlap_state = build_recall_overlap_state_from_views(
            recent_turns=selected_recent,
            compressed_notes=selected_compressed,
        )
        filtered_recall = self._filter_recall_candidates(
            recall_candidates=recall_candidates,
            overlap_state=overlap_state,
        )
        recall_filter_decisions = self._explain_recall_candidate_filtering(
            recall_candidates=recall_candidates,
            overlap_state=overlap_state,
        )
        recall_overlap_filter_reasons = [
            {
                "step_id": decision.step_id,
                "action_index": decision.action_index,
                "reason": decision.reason,
            }
            for decision in recall_filter_decisions
            if decision.filtered
        ]
        recall_selection_stop_reason = (
            "all_candidates_filtered_by_overlap"
            if recall_candidates and not filtered_recall
            else ""
        )
        recall_selection_stop_step_id: int | None = None
        recall_selection_stop_tokens: int | None = None
        recall_selection_budget: int | None = None

        for candidate in filtered_recall:
            candidate_recall = [*selected_recall, candidate]
            candidate_note = self.retrieval_policy.format_results(
                candidate_recall,
                title=recall_note_title,
            )
            candidate_note_tokens = self._count_tokens([self._assistant_message(candidate_note)])
            if candidate_note_tokens > recall_budget:
                recall_selection_stop_reason = "recall_budget_exceeded"
                recall_selection_stop_step_id = self._candidate_step_id(candidate)
                recall_selection_stop_tokens = candidate_note_tokens
                recall_selection_budget = recall_budget
                break
            candidate_messages = self._materialize(
                system_message=system_message,
                current_observation_message=current_observation_message,
                compressed_notes=selected_compressed,
                recent_turns=selected_recent,
                recall_note=candidate_note,
            )
            if self._count_tokens(candidate_messages) > prompt_budget:
                recall_selection_stop_reason = "prompt_budget_exceeded"
                recall_selection_stop_step_id = self._candidate_step_id(candidate)
                recall_selection_stop_tokens = self._count_tokens(candidate_messages)
                recall_selection_budget = prompt_budget
                break
            selected_recall = candidate_recall

        recall_note = ""
        if selected_recall:
            recall_note = self.retrieval_policy.format_results(
                selected_recall,
                title=recall_note_title,
            )

        openai_messages = self._materialize(
            system_message=system_message,
            current_observation_message=current_observation_message,
            compressed_notes=selected_compressed,
            recent_turns=selected_recent,
            recall_note=recall_note,
        )
        return PromptAssemblyResult(
            openai_messages=openai_messages,
            current_observation_message=current_observation_message,
            total_tokens=self._count_tokens(openai_messages),
            selected_recent_step_ids=[view.step_id for view in selected_recent],
            selected_compressed_keys=[
                f"{note.kind}:{note.sort_key}" for note in selected_compressed
            ],
            selected_recall_action_keys=[
                (int(item["step_id"]), int(item["action_index"]))
                for item in selected_recall
                if self._is_action_episode(item)
                and isinstance(item.get("step_id"), int)
                and isinstance(item.get("action_index"), int)
            ],
            selected_recall_step_ids=[
                int(item["step_id"])
                for item in selected_recall
                if isinstance(item.get("step_id"), int)
            ],
            selected_recall_count=len(selected_recall),
            selected_recall_items=[dict(item) for item in selected_recall],
            recall_candidate_count=len(recall_candidates),
            recall_overlap_filtered_count=len(recall_overlap_filter_reasons),
            recall_overlap_filtered_step_ids=[
                int(reason["step_id"])
                for reason in recall_overlap_filter_reasons
                if isinstance(reason.get("step_id"), int)
            ],
            recall_overlap_filter_reasons=recall_overlap_filter_reasons,
            recall_selection_stop_reason=recall_selection_stop_reason,
            recall_selection_stop_step_id=recall_selection_stop_step_id,
            recall_selection_stop_tokens=recall_selection_stop_tokens,
            recall_selection_budget=recall_selection_budget,
            budget_status="ok",
        )

    def _build_recent_turn_views(self, recent_segments: list[Any]) -> list[RecentTurnView]:
        views: list[RecentTurnView] = []
        recent_cap = self.runtime_settings.working_memory_budget.recent_step_cap
        for segment in recent_segments[-recent_cap:]:
            views.append(
                build_recent_turn_view(
                    segment,
                    summary_preset=self.runtime_settings.summary_preset,
                )
            )
        return views

    def _build_compressed_note_views(
        self,
        *,
        action_blocks: list[Any],
        heartbeat_ranges: list[Any],
    ) -> list[CompressedNoteView]:
        notes: list[CompressedNoteView] = []
        for block in action_blocks:
            notes.append(
                build_action_block_note_view(
                    block,
                    summary_preset=self.runtime_settings.summary_preset,
                )
            )
        for heartbeat in heartbeat_ranges:
            notes.append(
                build_heartbeat_note_view(
                    heartbeat,
                    summary_preset=self.runtime_settings.summary_preset,
                )
            )
        notes.sort(key=lambda item: item.sort_key)
        cap = self.runtime_settings.working_memory_budget.compressed_block_cap
        return notes[-cap:]

    def _filter_recall_candidates(
        self,
        *,
        recall_candidates: list[Mapping[str, Any]],
        overlap_state: RecallOverlapState,
    ) -> list[Mapping[str, Any]]:
        return filter_recall_candidates_by_overlap(recall_candidates, overlap_state)

    def _explain_recall_candidate_filtering(
        self,
        *,
        recall_candidates: list[Mapping[str, Any]],
        overlap_state: RecallOverlapState,
    ) -> list[RecallOverlapFilterDecision]:
        return explain_recall_candidates_by_overlap(recall_candidates, overlap_state)

    def _materialize(
        self,
        *,
        system_message: BaseMessage,
        current_observation_message: BaseMessage,
        compressed_notes: list[CompressedNoteView],
        recent_turns: list[RecentTurnView],
        recall_note: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            system_message.to_openai_message(OpenAIBackendRole.SYSTEM)
        ]
        for note in compressed_notes:
            messages.append(self._assistant_message(note.text))
        for turn in recent_turns:
            messages.extend(self._recent_turn_messages(turn))
        if recall_note:
            messages.append(self._assistant_message(recall_note))
        messages.append(current_observation_message.to_openai_message(OpenAIBackendRole.USER))
        return messages

    def _recent_turn_messages(self, view: RecentTurnView) -> list[dict[str, Any]]:
        return [
            BaseMessage.make_user_message(
                role_name="User",
                content=view.user_view,
            ).to_openai_message(OpenAIBackendRole.USER),
            BaseMessage.make_assistant_message(
                role_name="assistant",
                content=view.assistant_view,
            ).to_openai_message(OpenAIBackendRole.ASSISTANT),
        ]

    def _assistant_message(self, content: str) -> dict[str, Any]:
        return BaseMessage.make_assistant_message(
            role_name="assistant",
            content=content,
        ).to_openai_message(OpenAIBackendRole.ASSISTANT)

    def _count_tokens(self, messages: list[dict[str, Any]]) -> int:
        return self.runtime_settings.token_counter.count_tokens_from_messages(messages)

    def _is_action_episode(self, payload: Mapping[str, Any]) -> bool:
        return str(payload.get("memory_kind", "") or "") == "action_episode"

    def _candidate_step_id(self, payload: Mapping[str, Any]) -> int | None:
        step_id = payload.get("step_id")
        return step_id if isinstance(step_id, int) else None
