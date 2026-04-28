from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from .config import ActionV1RuntimeSettings
from .episodic_memory import ActionEpisode, HeartbeatRange, PlatformMemoryAdapter, StepSegment
from .memory_rendering import (
    build_action_block_note_view,
    build_heartbeat_note_view,
    build_recent_turn_view,
)
from .working_memory import (
    ActionSummaryBlock,
    MemoryState,
    build_action_summary_block,
    render_action_summary_block_text,
)


@dataclass(slots=True)
class ConsolidationOutcome:
    input_action_episodes: list[ActionEpisode] = field(default_factory=list)
    evicted_step_ids: list[int] = field(default_factory=list)
    merged_action_block_spans: list[tuple[int, int]] = field(default_factory=list)
    merged_heartbeat_ranges: list[tuple[int, int]] = field(default_factory=list)
    dropped_action_block_spans: list[tuple[int, int]] = field(default_factory=list)
    dropped_heartbeat_ranges: list[tuple[int, int]] = field(default_factory=list)


class Consolidator:
    def __init__(self, runtime_settings: ActionV1RuntimeSettings) -> None:
        self.runtime_settings = runtime_settings

    def maintain(
        self,
        *,
        memory_state: MemoryState,
        new_segment: StepSegment,
        action_episodes: list[ActionEpisode],
        adapter: PlatformMemoryAdapter,
    ) -> ConsolidationOutcome:
        memory_state.recent.segments.append(new_segment)
        memory_state.recent.step_action_episodes[new_segment.step_id] = list(
            action_episodes
        )
        outcome = ConsolidationOutcome(input_action_episodes=list(action_episodes))

        while (
            len(memory_state.recent.segments) > 1
            and self._recent_over_budget(memory_state.recent.segments)
        ):
            evicted = memory_state.recent.segments.pop(0)
            outcome.evicted_step_ids.append(evicted.step_id)
            evicted_episodes = memory_state.recent.step_action_episodes.pop(
                evicted.step_id,
                None,
            )
            if evicted_episodes is None:
                raise RuntimeError(
                    f"missing step_action_episodes for evicted step {evicted.step_id}"
                )
            self._consolidate_evicted_segment(
                memory_state=memory_state,
                segment=evicted,
                action_episodes=evicted_episodes,
                adapter=adapter,
            )

        self._enforce_compressed_budget(memory_state, outcome)
        return outcome

    def _recent_over_budget(self, segments: list[StepSegment]) -> bool:
        if len(segments) > self.runtime_settings.working_memory_budget.recent_step_cap:
            return True
        recent_budget = int(
            self.runtime_settings.effective_prompt_budget
            * self.runtime_settings.working_memory_budget.recent_budget_ratio
        )
        return self._recent_token_count(segments) > recent_budget

    def _recent_token_count(self, segments: Iterable[StepSegment]) -> int:
        total = 0
        for segment in segments:
            view = build_recent_turn_view(
                segment,
                summary_preset=self.runtime_settings.summary_preset,
            )
            messages = [
                BaseMessage.make_user_message(
                    role_name="User",
                    content=view.user_view,
                ).to_openai_message(OpenAIBackendRole.USER),
                BaseMessage.make_assistant_message(
                    role_name="assistant",
                    content=view.assistant_view,
                ).to_openai_message(OpenAIBackendRole.ASSISTANT),
            ]
            total += self.runtime_settings.token_counter.count_tokens_from_messages(messages)
        return total

    def _consolidate_evicted_segment(
        self,
        *,
        memory_state: MemoryState,
        segment: StepSegment,
        action_episodes: list[ActionEpisode],
        adapter: PlatformMemoryAdapter,
    ) -> None:
        block = build_action_summary_block(
            segment=segment,
            action_episodes=action_episodes,
            summary_preset=self.runtime_settings.summary_preset,
        )
        if block is not None:
            memory_state.compressed.action_blocks.append(block)
            return
        self._append_heartbeat(memory_state.compressed.heartbeat_ranges, segment, adapter)

    def _append_heartbeat(
        self,
        heartbeats: list[HeartbeatRange],
        segment: StepSegment,
        adapter: PlatformMemoryAdapter,
    ) -> None:
        digest = adapter.extract_topic(segment).strip() or adapter.extract_outcome(segment).strip()
        sampled_entities = adapter.extract_observed_entities(segment)[
            : self.runtime_settings.summary_preset.max_heartbeat_entity_samples
        ]
        if heartbeats and heartbeats[-1].end_step + 1 == segment.step_id:
            heartbeat = heartbeats[-1]
            heartbeat.end_step = segment.step_id
            heartbeat.end_timestamp = segment.timestamp
            heartbeat.count += 1
            heartbeat.last_digest = digest
            for entity in sampled_entities:
                if entity and entity not in heartbeat.sampled_entities:
                    heartbeat.sampled_entities.append(entity)
                if (
                    len(heartbeat.sampled_entities)
                    >= self.runtime_settings.summary_preset.max_entities_per_heartbeat
                ):
                    break
            return
        heartbeats.append(
            HeartbeatRange(
                agent_id=segment.agent_id,
                start_step=segment.step_id,
                end_step=segment.step_id,
                count=1,
                start_timestamp=segment.timestamp,
                end_timestamp=segment.timestamp,
                first_digest=digest,
                last_digest=digest,
                sampled_entities=sampled_entities,
            )
        )

    def _enforce_compressed_budget(
        self,
        memory_state: MemoryState,
        outcome: ConsolidationOutcome,
    ) -> None:
        while self._compressed_over_budget(memory_state):
            if self._merge_oldest_heartbeats(memory_state, outcome):
                continue
            if self._merge_oldest_action_blocks(memory_state, outcome):
                continue
            if self._drop_oldest_heartbeat(memory_state, outcome):
                continue
            if self._drop_oldest_action_block(memory_state, outcome):
                continue
            break

    def _compressed_over_budget(self, memory_state: MemoryState) -> bool:
        total_blocks = (
            len(memory_state.compressed.action_blocks)
            + len(memory_state.compressed.heartbeat_ranges)
        )
        if total_blocks > self.runtime_settings.working_memory_budget.compressed_block_cap:
            return True
        compressed_budget = int(
            self.runtime_settings.effective_prompt_budget
            * self.runtime_settings.working_memory_budget.compressed_budget_ratio
        )
        merge_trigger = int(
            compressed_budget
            * self.runtime_settings.working_memory_budget.compressed_merge_trigger_ratio
        )
        return self._compressed_token_count(memory_state) > merge_trigger

    def _compressed_token_count(self, memory_state: MemoryState) -> int:
        total = 0
        for block in memory_state.compressed.action_blocks:
            note = build_action_block_note_view(
                block,
                summary_preset=self.runtime_settings.summary_preset,
            )
            total += self.runtime_settings.token_counter.count_tokens_from_messages(
                [
                    BaseMessage.make_assistant_message(
                        role_name="assistant",
                        content=note.text,
                    ).to_openai_message(OpenAIBackendRole.ASSISTANT)
                ]
            )
        for heartbeat in memory_state.compressed.heartbeat_ranges:
            note = build_heartbeat_note_view(
                heartbeat,
                summary_preset=self.runtime_settings.summary_preset,
            )
            total += self.runtime_settings.token_counter.count_tokens_from_messages(
                [
                    BaseMessage.make_assistant_message(
                        role_name="assistant",
                        content=note.text,
                    ).to_openai_message(OpenAIBackendRole.ASSISTANT)
                ]
            )
        return total

    def _merge_oldest_heartbeats(
        self,
        memory_state: MemoryState,
        outcome: ConsolidationOutcome,
    ) -> bool:
        heartbeats = memory_state.compressed.heartbeat_ranges
        for index in range(len(heartbeats) - 1):
            first = heartbeats[index]
            second = heartbeats[index + 1]
            if first.end_step + 1 != second.start_step:
                continue
            merged = HeartbeatRange(
                agent_id=first.agent_id,
                start_step=first.start_step,
                end_step=second.end_step,
                count=first.count + second.count,
                start_timestamp=first.start_timestamp,
                end_timestamp=second.end_timestamp,
                first_digest=first.first_digest,
                last_digest=second.last_digest,
                sampled_entities=list(
                    dict.fromkeys([*first.sampled_entities, *second.sampled_entities])
                )[: self.runtime_settings.summary_preset.max_entities_per_heartbeat],
            )
            heartbeats[index : index + 2] = [merged]
            outcome.merged_heartbeat_ranges.append((merged.start_step, merged.end_step))
            return True
        return False

    def _merge_oldest_action_blocks(
        self,
        memory_state: MemoryState,
        outcome: ConsolidationOutcome,
    ) -> bool:
        blocks = memory_state.compressed.action_blocks
        max_span = self.runtime_settings.summary_preset.max_summary_merge_span
        for index in range(len(blocks) - 1):
            first = blocks[index]
            second = blocks[index + 1]
            if first.step_end + 1 != second.step_start:
                continue
            if second.step_end - first.step_start + 1 > max_span:
                continue
            merged = ActionSummaryBlock(
                memory_kind="action_summary_block",
                agent_id=first.agent_id,
                step_start=first.step_start,
                step_end=second.step_end,
                start_timestamp=first.start_timestamp,
                end_timestamp=second.end_timestamp,
                platform=first.platform,
                action_items=[*first.action_items, *second.action_items],
                topic=first.topic or second.topic,
                semantic_anchors=list(
                    dict.fromkeys([*first.semantic_anchors, *second.semantic_anchors])
                )[: self.runtime_settings.summary_preset.max_anchor_items_per_block],
                action_count=first.action_count + second.action_count,
                first_outcome_digest=first.first_outcome_digest,
                last_outcome_digest=second.last_outcome_digest,
                outcome_digest=second.last_outcome_digest or first.outcome_digest,
                source_action_keys=list(
                    dict.fromkeys([*first.source_action_keys, *second.source_action_keys])
                ),
                metadata={
                    "total_decision_count": int(first.metadata.get("total_decision_count", 0))
                    + int(second.metadata.get("total_decision_count", 0)),
                    "omitted_action_count": int(first.metadata.get("omitted_action_count", 0))
                    + int(second.metadata.get("omitted_action_count", 0)),
                },
            )
            merged.summary_text = render_action_summary_block_text(
                merged,
                summary_preset=self.runtime_settings.summary_preset,
            )
            blocks[index : index + 2] = [merged]
            outcome.merged_action_block_spans.append((merged.step_start, merged.step_end))
            return True
        return False

    def _drop_oldest_heartbeat(
        self,
        memory_state: MemoryState,
        outcome: ConsolidationOutcome,
    ) -> bool:
        if not memory_state.compressed.heartbeat_ranges:
            return False
        dropped = memory_state.compressed.heartbeat_ranges.pop(0)
        outcome.dropped_heartbeat_ranges.append((dropped.start_step, dropped.end_step))
        return True

    def _drop_oldest_action_block(
        self,
        memory_state: MemoryState,
        outcome: ConsolidationOutcome,
    ) -> bool:
        blocks = memory_state.compressed.action_blocks
        if not blocks:
            return False
        protected_count = (
            self.runtime_settings.summary_preset.compressed_action_block_drop_protected_count
        )
        if len(blocks) <= protected_count:
            return False
        dropped = blocks.pop(0)
        outcome.dropped_action_block_spans.append((dropped.step_start, dropped.step_end))
        return True
