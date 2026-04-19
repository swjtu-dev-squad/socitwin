from camel.messages import BaseMessage

from app.memory.config import (
    ActionV1RuntimeSettings,
    SummaryPresetConfig,
    TokenCounterLike,
    WorkingMemoryBudgetConfig,
)
from app.memory.consolidator import Consolidator
from app.memory.episodic_memory import (
    StepRecord,
    StepRecordKind,
    StepSegment,
    build_platform_memory_adapter,
)
from app.memory.working_memory import (
    CompressedWorkingMemory,
    MemoryState,
    RecentWorkingMemory,
)


class FixedTokenCounter(TokenCounterLike):
    def count_tokens_from_messages(self, messages) -> int:
        return sum(max(1, len(str(message.get("content", ""))) // 8) for message in messages)


def _make_segment(step_id: int, action_name: str) -> StepSegment:
    evidence = {
        "eligible_for_longterm": True,
        "target_type": "post" if "post" in action_name or action_name == "repost" else "user",
        "target_id": step_id,
        "target_snapshot": {
            "summary": f"target {step_id}",
            "evidence_quality": "normal",
            "degraded_evidence": False,
        },
        "target_visible_in_prompt": True,
        "target_resolution_status": "visible_in_prompt",
        "execution_status": "success",
        "local_context": {},
        "authored_content": "hello world" if action_name in {"create_post", "quote_post"} else "",
    }
    return StepSegment(
        agent_id="1",
        step_id=step_id,
        timestamp=float(step_id),
        platform="reddit",
        records=[
            StepRecord(
                role="user",
                kind=StepRecordKind.PERCEPTION,
                content=f"observation {step_id}",
                metadata={
                    "observation_prompt": f"observation {step_id}",
                    "topic": f"topic {step_id}",
                    "semantic_anchors": [f"anchor {step_id}"],
                    "entities": [f"post:{step_id}"],
                },
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.DECISION,
                content=f"{action_name}(target={step_id})",
                metadata={
                    "action_name": action_name,
                    "action": f"{action_name}(target={step_id})",
                    "action_evidence": evidence,
                },
            ),
            StepRecord(
                role="tool",
                kind=StepRecordKind.ACTION_RESULT,
                content=f"{action_name} result {step_id}",
                metadata={
                    "state_changes": [f"{action_name}:{step_id}"],
                    "action_evidence": evidence,
                },
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.FINAL_OUTCOME,
                content=f"final outcome {step_id}",
            ),
        ],
    )


def _settings(**kwargs) -> ActionV1RuntimeSettings:
    working_memory_budget = WorkingMemoryBudgetConfig(
        recent_budget_ratio=0.25,
        compressed_budget_ratio=0.15,
        recall_budget_ratio=0.10,
        recent_step_cap=kwargs.get("recent_step_cap", 1),
        compressed_block_cap=kwargs.get("compressed_block_cap", 4),
        compressed_merge_trigger_ratio=kwargs.get(
            "compressed_merge_trigger_ratio",
            1.0,
        ),
        generation_reserve_tokens=0,
    )
    return ActionV1RuntimeSettings(
        token_counter=FixedTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="system prompt",
        ),
        context_token_limit=4096,
        working_memory_budget=working_memory_budget,
        summary_preset=SummaryPresetConfig(),
    )


def test_consolidator_persists_longterm_candidates_before_recent_eviction() -> None:
    settings = _settings(recent_step_cap=3)
    consolidator = Consolidator(settings)
    adapter = build_platform_memory_adapter("reddit")
    state = MemoryState(
        recent=RecentWorkingMemory(),
        compressed=CompressedWorkingMemory(),
    )
    segment = _make_segment(1, "create_post")
    action_episodes = adapter.build_action_episodes(segment)

    outcome = consolidator.maintain(
        memory_state=state,
        new_segment=segment,
        action_episodes=action_episodes,
        adapter=adapter,
    )

    assert len(state.recent.segments) == 1
    assert len(outcome.input_action_episodes) == 1
    assert len(state.compressed.action_blocks) == 0


def test_consolidator_routes_low_significance_steps_to_heartbeat() -> None:
    settings = _settings(recent_step_cap=1)
    consolidator = Consolidator(settings)
    adapter = build_platform_memory_adapter("reddit")
    state = MemoryState(
        recent=RecentWorkingMemory(),
        compressed=CompressedWorkingMemory(),
    )

    first = _make_segment(1, "like_post")
    second = _make_segment(2, "create_post")
    consolidator.maintain(
        memory_state=state,
        new_segment=first,
        action_episodes=adapter.build_action_episodes(first),
        adapter=adapter,
    )
    consolidator.maintain(
        memory_state=state,
        new_segment=second,
        action_episodes=adapter.build_action_episodes(second),
        adapter=adapter,
    )

    assert [segment.step_id for segment in state.recent.segments] == [2]
    assert len(state.compressed.action_blocks) == 0
    assert len(state.compressed.heartbeat_ranges) == 1
    assert state.compressed.heartbeat_ranges[0].start_step == 1


def test_consolidator_builds_action_summary_block_with_exact_source_action_keys() -> None:
    settings = _settings(recent_step_cap=1)
    consolidator = Consolidator(settings)
    adapter = build_platform_memory_adapter("reddit")
    state = MemoryState(
        recent=RecentWorkingMemory(),
        compressed=CompressedWorkingMemory(),
    )

    first = _make_segment(1, "create_post")
    second = _make_segment(2, "follow")
    consolidator.maintain(
        memory_state=state,
        new_segment=first,
        action_episodes=adapter.build_action_episodes(first),
        adapter=adapter,
    )
    consolidator.maintain(
        memory_state=state,
        new_segment=second,
        action_episodes=adapter.build_action_episodes(second),
        adapter=adapter,
    )

    assert len(state.compressed.action_blocks) == 1
    block = state.compressed.action_blocks[0]
    assert (block.step_start, block.step_end) == (1, 1)
    assert block.source_action_keys == [(1, 0)]
    assert block.metadata["total_decision_count"] == 1
    assert block.metadata["omitted_action_count"] == 0
    assert block.action_items[0].target_evidence_quality == "normal"
    assert block.action_items[0].degraded_evidence is False


def test_consolidator_merges_oldest_adjacent_action_blocks_before_drop() -> None:
    settings = _settings(
        recent_step_cap=1,
        compressed_block_cap=1,
        compressed_merge_trigger_ratio=1.0,
    )
    consolidator = Consolidator(settings)
    adapter = build_platform_memory_adapter("reddit")
    state = MemoryState(
        recent=RecentWorkingMemory(),
        compressed=CompressedWorkingMemory(),
    )

    for step_id in (1, 2, 3):
        segment = _make_segment(step_id, "follow")
        consolidator.maintain(
            memory_state=state,
            new_segment=segment,
            action_episodes=adapter.build_action_episodes(segment),
            adapter=adapter,
        )

    assert [segment.step_id for segment in state.recent.segments] == [3]
    assert len(state.compressed.action_blocks) == 1
    merged = state.compressed.action_blocks[0]
    assert (merged.step_start, merged.step_end) == (1, 2)
