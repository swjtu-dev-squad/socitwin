from camel.messages import BaseMessage

from app.memory.config import (
    ActionV1RuntimeSettings,
    ObservationPresetConfig,
    RecallPresetConfig,
    TokenCounterLike,
)
from app.memory.episodic_memory import StepRecord, StepRecordKind, StepSegment
from app.memory.recall_planner import RecallPlanner, RecallPreparation, RecallRuntimeState
from app.memory.retrieval_policy import RetrievalPolicy
from app.memory.working_memory import (
    ActionItem,
    ActionSummaryBlock,
    CompressedWorkingMemory,
    MemoryState,
    RecentWorkingMemory,
)


class FixedTokenCounter(TokenCounterLike):
    def count_tokens_from_messages(self, messages) -> int:
        return sum(max(1, len(str(message.get("content", ""))) // 8) for message in messages)


class DummyLongtermStore:
    def __init__(self, episodes: list[dict]) -> None:
        self.episodes = list(episodes)

    def retrieve_relevant(
        self,
        query_text: str,
        *,
        limit: int,
        agent_id: str | int | None = None,
    ) -> list[dict]:
        del query_text
        items = self.episodes
        if agent_id is not None:
            items = [item for item in items if item.get("agent_id") == agent_id]
        return items[:limit]


def _settings(recall_preset: RecallPresetConfig | None = None) -> ActionV1RuntimeSettings:
    return ActionV1RuntimeSettings(
        token_counter=FixedTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="system prompt",
        ),
        context_token_limit=4096,
        observation_preset=ObservationPresetConfig(),
        recall_preset=recall_preset or RecallPresetConfig(),
    )


def _episode(step_id: int, agent_id: str = "1") -> dict:
    return {
        "memory_kind": "action_episode",
        "agent_id": agent_id,
        "step_id": step_id,
        "action_index": 0,
        "timestamp": float(step_id),
        "platform": "reddit",
        "action_name": "follow",
        "action_fact": f"follow(user_id={step_id})",
        "target_type": "user",
        "target_id": step_id,
        "target_snapshot": {"summary": f"user:{step_id}"},
        "target_visible_in_prompt": True,
        "target_resolution_status": "visible_in_prompt",
        "local_context": {},
        "authored_content": "",
        "state_changes": [],
        "execution_status": "success",
        "outcome": "ok",
        "topic": "",
        "query_source": "structured_event_query",
        "idle_step_gap": 0,
    }


def test_prepare_uses_last_successful_anchor_for_repeated_query_suppression() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(99)])
    runtime_state = RecallRuntimeState(
        last_successful_query_source="distilled_topic",
        last_successful_query_text="user:99",
        last_successful_step_id=1,
    )

    preparation = planner.prepare(
        topic="user:99",
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(),
        longterm_store=store,
        next_step_id=3,
        runtime_state=runtime_state,
    )

    assert preparation.retrieval_attempted is False
    assert preparation.candidates == []


def test_commit_selection_keeps_last_successful_anchor_when_nothing_injected() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    runtime_state = RecallRuntimeState(
        last_successful_query_source="distilled_topic",
        last_successful_query_text="older query",
        last_successful_step_id=2,
    )
    preparation = RecallPreparation(
        query_source="structured_event_query",
        query_text="new query",
        candidates=[_episode(5)],
        recalled_count=1,
        recalled_step_ids=[5],
        retrieval_attempted=True,
    )

    planner.commit_selection(
        runtime_state=runtime_state,
        preparation=preparation,
        selected_items=[],
        step_id=4,
    )

    assert runtime_state.last_successful_query_text == "older query"
    assert runtime_state.last_successful_step_id == 2
    assert runtime_state.last_recalled_count == 1
    assert runtime_state.last_recalled_step_ids == [5]
    assert runtime_state.last_injected_count == 0
    assert runtime_state.last_injected_step_ids == []


def test_prepare_does_not_use_entity_count_only_as_default_trigger() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8)])

    preparation = planner.prepare(
        entities=["user:8", "post:1", "comment:2"],
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(),
        longterm_store=store,
        next_step_id=1,
        runtime_state=RecallRuntimeState(),
    )

    assert preparation.retrieval_attempted is False
    assert preparation.query_text == ""
    assert preparation.recalled_count == 0


def test_prepare_uses_topic_trigger_when_present() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(RecallPresetConfig(min_trigger_entity_count=3)),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8)])

    preparation = planner.prepare(
        topic="topic query",
        entities=["user:8", "post:1", "comment:2"],
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(),
        longterm_store=store,
        next_step_id=1,
        runtime_state=RecallRuntimeState(),
    )

    assert preparation.retrieval_attempted is True
    assert preparation.query_text == "topic query"


def test_prepare_filters_longterm_results_by_agent_id() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8, "agent-a"), _episode(9, "agent-b")])

    preparation = planner.prepare(
        agent_id="agent-a",
        topic="user",
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(),
        longterm_store=store,
        next_step_id=1,
        runtime_state=RecallRuntimeState(),
    )

    assert preparation.retrieval_attempted is True
    assert [item["agent_id"] for item in preparation.candidates] == ["agent-a"]
    assert preparation.recalled_step_ids == [8]


def test_prepare_uses_anchor_only_trigger_when_present() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8)])

    preparation = planner.prepare(
        semantic_anchors=["post#8: safety review thread", "user#8: prior interaction"],
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(),
        longterm_store=store,
        next_step_id=1,
        runtime_state=RecallRuntimeState(),
    )

    assert preparation.retrieval_attempted is True
    assert preparation.query_text == "post#8: safety review thread user#8: prior interaction"
    assert preparation.gate_reason_flags.get("anchor_trigger") is True


def test_prepare_uses_recent_action_rehit_trigger() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8)])
    recent_segment = StepSegment(
        agent_id="a1",
        step_id=6,
        timestamp=6.0,
        platform="reddit",
        records=[
            StepRecord(
                role="assistant",
                kind=StepRecordKind.DECISION,
                content="like_post(post_id=8)",
                metadata={
                    "action_name": "like_post",
                    "action": "like_post(post_id=8)",
                    "action_evidence": {
                        "target_type": "post",
                        "target_id": 8,
                        "target_snapshot": {"summary": "post:8"},
                        "local_context": {},
                    },
                },
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.FINAL_OUTCOME,
                content="Acted on the visible post",
            ),
        ],
    )

    preparation = planner.prepare(
        snapshot={
            "posts": {"posts": [{"post_id": 8, "user_id": 2, "comments": []}]},
            "groups": {"all_groups": [], "messages": []},
        },
        memory_state=MemoryState(recent=RecentWorkingMemory(segments=[recent_segment])),
        longterm_store=store,
        next_step_id=7,
        runtime_state=RecallRuntimeState(),
    )

    assert preparation.retrieval_attempted is True
    assert preparation.gate_reason_flags.get("recent_action_trigger") is True
    assert bool(preparation.query_text) is True


def test_prepare_blocks_weak_recent_episode_query_during_cooldown() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8)])
    recent_segment = StepSegment(
        agent_id="a1",
        step_id=6,
        timestamp=6.0,
        platform="reddit",
        records=[
            StepRecord(
                role="assistant",
                kind=StepRecordKind.DECISION,
                content="do_nothing()",
                metadata={"action_name": "do_nothing", "action": "do_nothing()"},
            ),
            StepRecord(
                role="assistant",
                kind=StepRecordKind.FINAL_OUTCOME,
                content="Quiet step outcome",
            ),
        ],
    )

    preparation = planner.prepare(
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(recent=RecentWorkingMemory(segments=[recent_segment])),
        longterm_store=store,
        next_step_id=7,
        runtime_state=RecallRuntimeState(
            last_successful_query_source="recent_episodic_summary",
            last_successful_query_text="older recall",
            last_successful_step_id=6,
        ),
    )

    assert preparation.retrieval_attempted is False
    assert preparation.gate_decision is False
    assert preparation.gate_reason_flags.get("cooldown_blocked") is True


def test_prepare_leaves_overlap_suppression_to_prompt_assembler() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(),
        retrieval_policy=RetrievalPolicy(),
    )
    store = DummyLongtermStore([_episode(8)])

    preparation = planner.prepare(
        topic="user:8",
        entities=["user:8"],
        snapshot={"posts": {"posts": []}, "groups": {"all_groups": [], "messages": []}},
        memory_state=MemoryState(
            recent=RecentWorkingMemory(),
            compressed=CompressedWorkingMemory(
                action_blocks=[
                    ActionSummaryBlock(
                        memory_kind="action_summary_block",
                        agent_id="1",
                        step_start=8,
                        step_end=8,
                        start_timestamp=8.0,
                        end_timestamp=8.0,
                        platform="reddit",
                        action_items=[
                            ActionItem(
                                step_id=8,
                                action_index=0,
                                action_name="follow",
                                action_fact="follow(user_id=8)",
                            )
                        ],
                        action_count=1,
                        source_action_keys=[(8, 0)],
                    )
                ],
            ),
        ),
        longterm_store=store,
        next_step_id=1,
        runtime_state=RecallRuntimeState(),
    )

    assert preparation.retrieval_attempted is True
    assert preparation.recalled_count == 1
    assert preparation.recalled_step_ids == [8]


def test_commit_selection_respects_reason_trace_char_budget() -> None:
    planner = RecallPlanner(
        runtime_settings=_settings(RecallPresetConfig(max_reason_trace_chars=5)),
        retrieval_policy=RetrievalPolicy(),
    )
    runtime_state = RecallRuntimeState()
    preparation = RecallPreparation(
        query_source="structured_event_query",
        query_text="user:55",
        retrieval_attempted=True,
    )

    planner.commit_selection(
        runtime_state=runtime_state,
        preparation=preparation,
        selected_items=[
            {
                "memory_kind": "action_episode",
                "step_id": 55,
                "action_index": 0,
                "action_name": "follow",
                "action_fact": "follow(user_id=55)",
                "target_snapshot": {"summary": "target summary"},
            }
        ],
        step_id=9,
    )

    assert runtime_state.last_reason_trace == "targe"
