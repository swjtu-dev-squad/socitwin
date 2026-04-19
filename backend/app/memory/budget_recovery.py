from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .config import ActionV1RuntimeSettings, ObservationPresetConfig
from .observation_shaper import (
    ObservationArtifact,
    ObservationShaper,
    build_minimal_bounded_visible_payload,
)
from .working_memory import CompressedWorkingMemory, MemoryState, RecentWorkingMemory


@dataclass(slots=True)
class BudgetRecoveryState:
    attempt_index: int = 0
    stage: str = "normal"
    pressure_level: str = "normal"
    provider_overflow_count: int = 0
    include_recall: bool = True
    include_compressed: bool = True
    observation_reduction_level: int = 0
    recent_step_cap_override: int | None = None
    generation_reserve_penalty: int = 0


class BudgetRecoveryController:
    def __init__(self, runtime_settings: ActionV1RuntimeSettings) -> None:
        self.runtime_settings = runtime_settings

    def initial_state(self) -> BudgetRecoveryState:
        return BudgetRecoveryState()

    def effective_prompt_budget(self, *, state: BudgetRecoveryState) -> int:
        return max(
            1,
            self.runtime_settings.effective_prompt_budget - state.generation_reserve_penalty,
        )

    def next_for_local_over_budget(
        self,
        *,
        state: BudgetRecoveryState,
    ) -> BudgetRecoveryState | None:
        return self._advance(state=state, pressure_level="local_over_budget")

    def next_for_provider_overflow(
        self,
        *,
        state: BudgetRecoveryState,
    ) -> BudgetRecoveryState | None:
        updated = replace(
            state,
            provider_overflow_count=state.provider_overflow_count + 1,
        )
        if updated.provider_overflow_count >= 2:
            updated = replace(
                updated,
                generation_reserve_penalty=max(
                    updated.generation_reserve_penalty,
                    max(128, self.runtime_settings.working_memory_budget.generation_reserve_tokens // 4),
                ),
            )
        return self._advance(state=updated, pressure_level="provider_overflow")

    def derived_memory_state(
        self,
        *,
        memory_state: MemoryState,
        state: BudgetRecoveryState,
    ) -> MemoryState:
        recent_segments = list(memory_state.recent.segments)
        if state.recent_step_cap_override is not None:
            recent_segments = recent_segments[-state.recent_step_cap_override :]

        compressed = memory_state.compressed
        derived_compressed = (
            CompressedWorkingMemory(
                action_blocks=list(compressed.action_blocks),
                heartbeat_ranges=list(compressed.heartbeat_ranges),
            )
            if state.include_compressed
            else CompressedWorkingMemory()
        )

        return MemoryState(
            recent=RecentWorkingMemory(
                segments=recent_segments,
                step_action_episodes={
                    segment.step_id: list(
                        memory_state.recent.step_action_episodes.get(segment.step_id, [])
                    )
                    for segment in recent_segments
                },
            ),
            compressed=derived_compressed,
        )

    def derive_recall_candidates(
        self,
        *,
        recall_candidates: Sequence[Mapping[str, Any]],
        state: BudgetRecoveryState,
    ) -> list[dict[str, Any]]:
        if not state.include_recall:
            return []
        return [dict(item) for item in recall_candidates]

    def observation_artifact_for_state(
        self,
        *,
        base_artifact: ObservationArtifact,
        raw_payload: dict[str, Any] | None,
        current_agent_id: Any,
        state: BudgetRecoveryState,
    ) -> ObservationArtifact:
        if state.observation_reduction_level <= 0 or not raw_payload:
            return copy.deepcopy(base_artifact)

        if state.observation_reduction_level >= 2:
            minimal_payload = build_minimal_bounded_visible_payload(
                self.runtime_settings.observation_preset
            )
            temp_settings = replace(
                self.runtime_settings,
                observation_preset=self.runtime_settings.observation_preset,
            )
            return ObservationShaper(temp_settings).shape(
                posts_payload=minimal_payload["posts"],
                groups_payload=minimal_payload["groups"],
                current_agent_id=current_agent_id,
            )

        temp_settings = replace(
            self.runtime_settings,
            observation_preset=self._tightened_observation_preset(level=1),
        )
        return ObservationShaper(temp_settings).shape(
            posts_payload=copy.deepcopy(raw_payload.get("posts", {})),
            groups_payload=copy.deepcopy(raw_payload.get("groups", {})),
            current_agent_id=current_agent_id,
        )

    def _advance(
        self,
        *,
        state: BudgetRecoveryState,
        pressure_level: str,
    ) -> BudgetRecoveryState | None:
        if state.attempt_index >= self.runtime_settings.provider_runtime_preset.max_budget_retries:
            return None

        next_state = replace(
            state,
            attempt_index=state.attempt_index + 1,
            pressure_level=pressure_level,
        )

        if next_state.include_recall:
            return replace(next_state, include_recall=False, stage="drop_recall")
        if next_state.include_compressed:
            return replace(next_state, include_compressed=False, stage="drop_compressed")
        if next_state.observation_reduction_level < 1:
            return replace(
                next_state,
                observation_reduction_level=1,
                stage="strong_observation_reduction",
            )
        if next_state.observation_reduction_level < 2:
            return replace(
                next_state,
                observation_reduction_level=2,
                stage="minimal_physical_fallback",
            )
        return None

    def _tightened_observation_preset(self, *, level: int) -> ObservationPresetConfig:
        del level
        preset = self.runtime_settings.observation_preset
        return replace(
            preset,
            groups_count_guard=min(preset.groups_count_guard, 16),
            comments_total_guard=min(preset.comments_total_guard, 64),
            messages_total_guard=min(preset.messages_total_guard, 64),
            post_text_cap_chars=min(preset.post_text_cap_chars, 600),
            comment_text_cap_chars=min(preset.comment_text_cap_chars, 400),
            message_text_cap_chars=min(preset.message_text_cap_chars, 160),
        )
