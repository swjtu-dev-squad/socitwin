from camel.messages import BaseMessage

from app.memory.config import (
    ActionV1RuntimeSettings,
    ObservationPresetConfig,
    SummaryPresetConfig,
    TokenCounterLike,
    WorkingMemoryBudgetConfig,
)
from app.memory.episodic_memory import (
    EpisodeRecord,
    HeartbeatRange,
    StepRecord,
    StepRecordKind,
    StepSegment,
)
from app.memory.prompt_assembler import PromptAssembler
from app.memory.retrieval_policy import RetrievalPolicy
from app.memory.working_memory import (
    ActionItem,
    ActionSummaryBlock,
    CompressedWorkingMemory,
    MemoryState,
    RecentWorkingMemory,
    episode_record_to_action_summary_block,
)


class FixedTokenCounter(TokenCounterLike):
    def count_tokens_from_messages(self, messages) -> int:
        return sum(max(1, len(str(message.get("content", ""))) // 8) for message in messages)


def _build_settings() -> ActionV1RuntimeSettings:
    return ActionV1RuntimeSettings(
        token_counter=FixedTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="system prompt",
        ),
        context_token_limit=4096,
        observation_preset=ObservationPresetConfig(),
        working_memory_budget=WorkingMemoryBudgetConfig(
            recent_budget_ratio=0.25,
            compressed_budget_ratio=0.15,
            recall_budget_ratio=0.10,
            recent_step_cap=3,
            generation_reserve_tokens=256,
        ),
        summary_preset=SummaryPresetConfig(),
    )


def test_prompt_assembler_materializes_fixed_message_shape() -> None:
    assembler = PromptAssembler(
        runtime_settings=_build_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    recent_segment = StepSegment(
        agent_id="a1",
        step_id=5,
        timestamp=1.0,
        platform="reddit",
        records=[
            StepRecord(
                role="user",
                kind=StepRecordKind.PERCEPTION,
                content="wrapped prompt",
                metadata={"observation_prompt": "visible observation"},
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.DECISION,
                content="like_post(post_id=9)",
                metadata={
                    "action": "like_post(post_id=9)",
                    "action_evidence": {
                        "execution_status": "success",
                        "target_type": "post",
                        "target_id": 9,
                        "target_snapshot": {"summary": "Interesting post"},
                    },
                },
            ),
            StepRecord(
                role="tool",
                kind=StepRecordKind.ACTION_RESULT,
                content="ok",
                metadata={"state_changes": ["liked_post:9"]},
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.FINAL_OUTCOME,
                content="Final answer",
            ),
        ],
    )
    episode = EpisodeRecord(
        agent_id="a1",
        step_id=3,
        timestamp=0.5,
        platform="reddit",
        actions=["follow(user_id=2)"],
        semantic_anchors=["anchor one"],
        outcome="earlier outcome",
    )
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
    recall_item = {
        "memory_kind": "action_episode",
        "step_id": 20,
        "action_index": 0,
        "platform": "reddit",
        "action_name": "follow",
        "action_fact": "follow(user_id=4)",
        "target_type": "user",
        "target_id": 4,
        "target_snapshot": {"summary": "user:4"},
        "local_context": {},
        "state_changes": ["followed_user:4"],
        "outcome": "success",
    }

    result = assembler.assemble(
        system_message=_build_settings().system_message,
        current_observation_prompt="current observation",
        memory_state=MemoryState(
            recent=RecentWorkingMemory(segments=[recent_segment]),
            compressed=CompressedWorkingMemory(
                action_blocks=[episode_record_to_action_summary_block(episode)],
                heartbeat_ranges=[heartbeat],
            ),
        ),
        recall_candidates=[recall_item],
    )

    roles = [message["role"] for message in result.openai_messages]
    assert roles == [
        "system",
        "assistant",
        "assistant",
        "user",
        "assistant",
        "assistant",
        "user",
    ]
    contents = [message["content"] for message in result.openai_messages]
    assert contents[1].startswith("Compressed short-term memory:")
    assert contents[2].startswith("Compressed short-term memory:")
    assert contents[3].startswith("<historical_observation>\nvisible observation")
    assert "Actions:" in contents[4]
    assert contents[5].startswith("Relevant long-term memory:")
    assert "current observation" in contents[6]
    assert result.selected_recent_step_ids == [5]
    assert result.selected_recall_count == 1
    assert result.recall_candidate_count == 1
    assert result.recall_overlap_filtered_count == 0


def test_prompt_assembler_suppresses_recall_for_compressed_step_overlap() -> None:
    assembler = PromptAssembler(
        runtime_settings=_build_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    episode = EpisodeRecord(
        agent_id="a1",
        step_id=3,
        timestamp=0.5,
        platform="reddit",
        actions=["follow(user_id=2)"],
        semantic_anchors=["anchor one"],
        outcome="earlier outcome",
    )
    overlapping_recall_item = {
        "memory_kind": "action_episode",
        "step_id": 3,
        "action_index": 0,
        "platform": "reddit",
        "action_name": "follow",
        "action_fact": "follow(user_id=2)",
        "target_type": "user",
        "target_id": 2,
        "target_snapshot": {"summary": "user:2"},
        "local_context": {},
        "state_changes": ["followed_user:2"],
        "outcome": "success",
    }

    result = assembler.assemble(
        system_message=_build_settings().system_message,
        current_observation_prompt="current observation",
        memory_state=MemoryState(
            recent=RecentWorkingMemory(),
            compressed=CompressedWorkingMemory(
                action_blocks=[episode_record_to_action_summary_block(episode)],
                heartbeat_ranges=[],
            ),
        ),
        recall_candidates=[overlapping_recall_item],
    )

    assert result.selected_recall_count == 0
    assert result.recall_overlap_filtered_count == 1
    assert result.recall_overlap_filtered_step_ids == [3]
    assert (
        result.recall_overlap_filter_reasons[0]["reason"]
        == "compressed_conservative_step_overlap"
    )
    assert result.recall_selection_stop_reason == "all_candidates_filtered_by_overlap"


def test_prompt_assembler_only_exact_key_suppresses_for_nonlegacy_action_block() -> None:
    assembler = PromptAssembler(
        runtime_settings=_build_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    block = ActionSummaryBlock(
        memory_kind="action_summary_block",
        agent_id="a1",
        step_start=3,
        step_end=3,
        start_timestamp=0.5,
        end_timestamp=0.5,
        platform="reddit",
        action_items=[
            ActionItem(
                step_id=3,
                action_index=0,
                action_name="follow",
                action_fact="follow(user_id=2)",
            )
        ],
        action_count=1,
        source_action_keys=[(3, 0)],
        summary_text="compressed",
    )
    retained_recall_item = {
        "memory_kind": "action_episode",
        "step_id": 3,
        "action_index": 1,
        "platform": "reddit",
        "action_name": "mute",
        "action_fact": "mute(user_id=2)",
        "target_type": "user",
        "target_id": 2,
        "target_snapshot": {"summary": "user:2"},
        "local_context": {},
        "state_changes": ["muted_user:2"],
        "outcome": "success",
    }

    result = assembler.assemble(
        system_message=_build_settings().system_message,
        current_observation_prompt="current observation",
        memory_state=MemoryState(
            recent=RecentWorkingMemory(),
            compressed=CompressedWorkingMemory(
                action_blocks=[block],
                heartbeat_ranges=[],
            ),
        ),
        recall_candidates=[retained_recall_item],
    )

    assert result.selected_recall_count == 1
    assert result.recall_overlap_filtered_count == 0


def test_prompt_assembler_returns_base_over_budget_failure() -> None:
    settings = ActionV1RuntimeSettings(
        token_counter=FixedTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="system prompt",
        ),
        context_token_limit=20,
        working_memory_budget=WorkingMemoryBudgetConfig(generation_reserve_tokens=0),
        summary_preset=SummaryPresetConfig(),
    )
    assembler = PromptAssembler(
        runtime_settings=settings,
        retrieval_policy=RetrievalPolicy(),
    )

    result = assembler.assemble(
        system_message=settings.system_message,
        current_observation_prompt="very long current observation that cannot fit",
        memory_state=MemoryState(),
        recall_candidates=[],
    )

    assert result.budget_status == "base_prompt_over_budget"
    assert result.assembly_failure_reason == "base_prompt_exceeds_effective_prompt_budget"
