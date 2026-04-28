from app.memory.config import SummaryPresetConfig
from app.memory.episodic_memory import (
    ActionEpisode,
    EpisodeRecord,
    HeartbeatRange,
    StepRecord,
    StepRecordKind,
    StepSegment,
)
from app.memory.memory_rendering import (
    build_action_block_note_view,
    build_heartbeat_note_view,
    build_recent_turn_view,
)
from app.memory.working_memory import (
    ActionSummaryBlock,
    CompressedWorkingMemory,
    MemoryState,
    RecentWorkingMemory,
    build_action_summary_block,
    build_recall_overlap_state_from_memory_state,
    episode_record_to_action_summary_block,
    explain_recall_candidates_by_overlap,
    filter_recall_candidates_by_overlap,
)


def make_segment(step_id: int, action_name: str, execution_status: str = "success") -> StepSegment:
    evidence = {
        "execution_status": execution_status,
        "target_type": "post",
        "target_id": step_id,
        "target_snapshot": {"summary": f"target {step_id}", "evidence_quality": "normal"},
        "local_context": {},
    }
    return StepSegment(
        agent_id="a1",
        step_id=step_id,
        timestamp=float(step_id),
        platform="reddit",
        records=[
            StepRecord(
                role="user",
                kind=StepRecordKind.PERCEPTION,
                content=f"observation {step_id}",
                metadata={
                    "observation_prompt": f"visible observation {step_id}",
                    "topic": f"topic {step_id}",
                    "semantic_anchors": [f"anchor {step_id}"],
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
                content=f"result {step_id}",
                metadata={"state_changes": [f"{action_name}:{step_id}"]},
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.FINAL_OUTCOME,
                content=f"final outcome {step_id}",
            ),
        ],
    )


def make_action_episode(step_id: int, action_name: str) -> ActionEpisode:
    return ActionEpisode(
        agent_id="a1",
        step_id=step_id,
        action_index=0,
        timestamp=float(step_id),
        platform="reddit",
        action_name=action_name,
        action_fact=f"{action_name}(target={step_id})",
        target_type="post",
        target_id=step_id,
        target_snapshot={"summary": f"target {step_id}", "evidence_quality": "normal"},
        execution_status="success",
        action_significance="high" if action_name == "create_post" else "medium",
    )


def test_build_action_summary_block_keeps_memory_worthy_actions() -> None:
    segment = make_segment(1, "create_post")
    block = build_action_summary_block(
        segment=segment,
        action_episodes=[make_action_episode(1, "create_post")],
        summary_preset=SummaryPresetConfig(),
    )

    assert block is not None
    assert block.source_action_keys == [(1, 0)]
    assert block.action_items[0].target_summary == "target 1"


def test_episode_record_to_action_summary_block_marks_legacy_metadata() -> None:
    episode = EpisodeRecord(
        agent_id="a1",
        step_id=3,
        timestamp=0.5,
        platform="reddit",
        actions=["follow(user_id=2)"],
        semantic_anchors=["anchor one"],
        outcome="earlier outcome",
    )
    block = episode_record_to_action_summary_block(episode)
    assert block.metadata["legacy_episode_record"] is True
    assert block.action_count == 1


def test_recent_and_compressed_views_render_expected_shapes() -> None:
    summary_preset = SummaryPresetConfig()
    segment = make_segment(5, "like_post")
    recent_view = build_recent_turn_view(segment, summary_preset=summary_preset)
    assert recent_view.user_view.startswith("<historical_observation>\nvisible observation 5")
    assert "Actions:" in recent_view.assistant_view

    block = ActionSummaryBlock(
        memory_kind="action_summary_block",
        agent_id="a1",
        step_start=3,
        step_end=3,
        start_timestamp=0.5,
        end_timestamp=0.5,
        platform="reddit",
        action_items=[],
        source_action_keys=[],
    )
    note = build_action_block_note_view(block, summary_preset=summary_preset)
    assert note.kind == "action_block"

    heartbeat = HeartbeatRange(
        agent_id="a1",
        start_step=1,
        end_step=2,
        count=2,
        start_timestamp=0.1,
        end_timestamp=0.4,
        first_digest="first",
        last_digest="last",
        sampled_entities=["post:1"],
    )
    heartbeat_note = build_heartbeat_note_view(heartbeat, summary_preset=summary_preset)
    assert heartbeat_note.kind == "heartbeat"


def test_overlap_filters_exact_and_conservative_matches() -> None:
    memory_state = MemoryState(
        recent=RecentWorkingMemory(segments=[make_segment(5, "like_post")]),
        compressed=CompressedWorkingMemory(
            action_blocks=[
                ActionSummaryBlock(
                    memory_kind="action_summary_block",
                    agent_id="a1",
                    step_start=3,
                    step_end=3,
                    start_timestamp=0.5,
                    end_timestamp=0.5,
                    platform="reddit",
                    action_items=[],
                    source_action_keys=[(3, 0)],
                )
            ],
            heartbeat_ranges=[
                HeartbeatRange(
                    agent_id="a1",
                    start_step=1,
                    end_step=2,
                    count=2,
                    start_timestamp=0.1,
                    end_timestamp=0.4,
                )
            ],
        ),
    )
    overlap_state = build_recall_overlap_state_from_memory_state(memory_state)
    candidates = [
        {"memory_kind": "action_episode", "step_id": 3, "action_index": 0},
        {"memory_kind": "action_episode", "step_id": 2, "action_index": 0},
        {"memory_kind": "action_episode", "step_id": 8, "action_index": 0},
    ]

    kept = filter_recall_candidates_by_overlap(candidates, overlap_state)
    decisions = explain_recall_candidates_by_overlap(candidates, overlap_state)

    assert kept == [{"memory_kind": "action_episode", "step_id": 8, "action_index": 0}]
    assert decisions[0].reason == "compressed_exact_action_overlap"
    assert decisions[1].reason == "compressed_conservative_step_overlap"
