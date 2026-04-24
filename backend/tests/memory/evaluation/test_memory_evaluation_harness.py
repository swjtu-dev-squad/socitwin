from __future__ import annotations

import inspect
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.memory.config import MemoryMode
from app.memory.evaluation_harness import (
    EvaluationConfig,
    EvaluationEvent,
    EvaluationRecorder,
    _build_real_longwindow_events,
    _build_real_scenario_events,
    _run_comparison,
    _summarize_comparison_run,
    build_parser,
    parse_args,
    run_memory_evaluation,
)


def test_run_memory_evaluation_writes_summary_and_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch(
            "app.memory.evaluation_harness._preflight_embedding",
            return_value=EvaluationEvent(
                phase="preflight",
                name="embedding_openai_compatible",
                status="pass",
            )
        ):
            result = run_memory_evaluation(
                EvaluationConfig(
                    phases=["preflight", "deterministic"],
                    output_dir=Path(tmp),
                    run_id="deterministic-test",
                )
            )

        run_dir = Path(result["run_dir"])
        assert (run_dir / "config.json").exists()
        assert (run_dir / "events.jsonl").exists()
        assert (run_dir / "summary.json").exists()
        assert (run_dir / "README.md").exists()

        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        assert summary["summary"]["success"] is True
        assert "preflight" in summary["summary"]["by_phase"]
        assert "deterministic" in summary["summary"]["by_phase"]
        assert summary["memory_kpis"]["ltm_exact_hit_at_3"] is None
        assert summary["memory_kpis"]["recall_injection_trace_rate"] is None
        assert any(
            item["metric"] == "ltm_exact_hit_at_3"
            for item in summary["unavailable_metrics"]
        )

        readme = (run_dir / "README.md").read_text(encoding="utf-8")
        assert "## Memory KPIs" in readme
        assert "## Unavailable Metrics" in readme

        events = [
            json.loads(line)
            for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        event_names = {event["name"] for event in events}
        assert "chromadb_dependency_available" in event_names
        assert "embedding_openai_compatible" in event_names
        assert "VAL-OBS-01 long_text_post_fidelity" in event_names
        assert "VAL-RCL-02 strong_signal_recall_trigger" in event_names


def test_evaluation_recorder_aggregates_memory_kpis() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        recorder = EvaluationRecorder(Path(tmp) / "kpi-test")
        recorder.record(
            EvaluationEvent(
                phase="real-scenarios",
                name="VAL-LTM-05 real_self_action_retrievability",
                status="pass",
                metrics={
                    "hit_at_1": 0.5,
                    "hit_at_3": 1.0,
                    "mrr": 0.75,
                    "cross_agent_top3_count": 1,
                    "top3_candidate_slot_count": 4,
                },
            )
        )
        recorder.record(
            EvaluationEvent(
                phase="real-scenarios",
                name="VAL-RCL-08 real_continuity_recall_probe",
                status="pass",
                metrics={"gate_decision": True},
            )
        )
        recorder.record(
            EvaluationEvent(
                phase="real-scenarios",
                name="VAL-RCL-09 real_empty_observation_recall_suppression",
                status="pass",
                metrics={
                    "gate_decision": False,
                    "retrieval_attempted": False,
                    "recalled_count": 0,
                },
            )
        )
        recorder.record(
            EvaluationEvent(
                phase="real-longwindow",
                name="VAL-RCL-10 real_longwindow_recall_injection",
                status="pass",
                metrics={
                    "recall_recalled_trace_count": 4,
                    "recall_injected_trace_count": 3,
                },
            )
        )

        recorder.finalize(EvaluationConfig(output_dir=Path(tmp), run_id="kpi-test"))

        summary = json.loads(
            (Path(tmp) / "kpi-test" / "summary.json").read_text(encoding="utf-8")
        )
        assert summary["memory_kpis"] == {
            "ltm_exact_hit_at_1": 0.5,
            "ltm_exact_hit_at_3": 1.0,
            "ltm_mrr": 0.75,
            "cross_agent_contamination_rate": 0.25,
            "recall_gate_success_rate": 1.0,
            "false_recall_trigger_rate": 0.0,
            "recall_injection_trace_rate": 0.75,
        }
        assert summary["unavailable_metrics"] == []


def test_parser_accepts_multiple_phases() -> None:
    args = build_parser().parse_args(["--phase", "preflight", "--phase", "deterministic"])
    config = parse_args(["--phase", "preflight", "--phase", "deterministic"])

    assert args.phase == ["preflight", "deterministic"]
    assert config.phases == ["preflight", "deterministic"]


def test_parser_accepts_real_smoke_phase() -> None:
    args = build_parser().parse_args(
        ["--phase", "real-smoke", "--smoke-agent-count", "2"]
    )
    config = parse_args(["--phase", "real-smoke", "--smoke-agent-count", "2"])

    assert args.phase == ["real-smoke"]
    assert config.phases == ["real-smoke"]
    assert config.smoke_agent_count == 2
    assert config.smoke_timeout_seconds == 60


def test_parser_accepts_real_scenarios_phase() -> None:
    args = build_parser().parse_args(
        ["--phase", "real-scenarios", "--scenario-agent-count", "3", "--scenario-steps", "4"]
    )
    config = parse_args(
        ["--phase", "real-scenarios", "--scenario-agent-count", "3", "--scenario-steps", "4"]
    )

    assert args.phase == ["real-scenarios"]
    assert config.phases == ["real-scenarios"]
    assert config.scenario_agent_count == 3
    assert config.scenario_steps == 4


def test_parser_accepts_real_longwindow_phase() -> None:
    args = build_parser().parse_args(
        ["--phase", "real-longwindow", "--longwindow-agent-count", "3", "--longwindow-steps", "9"]
    )
    config = parse_args(
        ["--phase", "real-longwindow", "--longwindow-agent-count", "3", "--longwindow-steps", "9"]
    )

    assert args.phase == ["real-longwindow"]
    assert config.phases == ["real-longwindow"]
    assert config.longwindow_agent_count == 3
    assert config.longwindow_steps == 9


def test_parser_accepts_comparison_phase() -> None:
    args = build_parser().parse_args(
        ["--phase", "comparison", "--comparison-agent-count", "3", "--comparison-steps", "10"]
    )
    config = parse_args(
        ["--phase", "comparison", "--comparison-agent-count", "3", "--comparison-steps", "10"]
    )

    assert args.phase == ["comparison"]
    assert config.phases == ["comparison"]
    assert config.comparison_agent_count == 3
    assert config.comparison_steps == 10


def test_run_memory_evaluation_dispatches_real_smoke_phase() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch(
            "app.memory.evaluation_harness._run_real_smoke"
        ) as real_smoke:
            run_memory_evaluation(
                EvaluationConfig(
                    phases=["real-smoke"],
                    output_dir=Path(tmp),
                    run_id="real-smoke-test",
                )
            )

    real_smoke.assert_called_once()


def test_run_memory_evaluation_dispatches_real_scenarios_phase() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch(
            "app.memory.evaluation_harness._run_real_scenarios"
        ) as real_scenarios:
            run_memory_evaluation(
                EvaluationConfig(
                    phases=["real-scenarios"],
                    output_dir=Path(tmp),
                    run_id="real-scenarios-test",
                )
            )

    real_scenarios.assert_called_once()


def test_run_memory_evaluation_dispatches_real_longwindow_phase() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch(
            "app.memory.evaluation_harness._run_real_longwindow"
        ) as real_longwindow:
            run_memory_evaluation(
                EvaluationConfig(
                    phases=["real-longwindow"],
                    output_dir=Path(tmp),
                    run_id="real-longwindow-test",
                )
            )

    real_longwindow.assert_called_once()


def test_run_memory_evaluation_dispatches_comparison_phase() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        with patch(
            "app.memory.evaluation_harness._run_comparison"
        ) as comparison:
            run_memory_evaluation(
                EvaluationConfig(
                    phases=["comparison"],
                    output_dir=Path(tmp),
                    run_id="comparison-test",
                )
            )

    comparison.assert_called_once()


def test_run_comparison_blocks_action_v1_when_embedding_preflight_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        recorder = EvaluationRecorder(Path(tmp))
        upstream_event = EvaluationEvent(
            phase="comparison",
            name="upstream_short_comparison",
            status="pass",
            metrics={"memory_mode": "upstream"},
        )

        def _fake_asyncio_run(awaitable):
            if inspect.iscoroutine(awaitable):
                awaitable.close()
            return upstream_event

        with (
            patch(
                "app.memory.evaluation_harness._preflight_embedding",
                return_value=EvaluationEvent(
                    phase="preflight",
                    name="embedding_openai_compatible",
                    status="blocked",
                    metrics={"embedding_url": "http://127.0.0.1:11434/v1"},
                    reason="connection refused",
                ),
            ),
            patch(
                "app.memory.evaluation_harness.asyncio.run",
                side_effect=_fake_asyncio_run,
            ) as run_async,
        ):
            _run_comparison(
                EvaluationConfig(
                    phases=["comparison"],
                    output_dir=Path(tmp),
                    run_id="comparison-blocked-test",
                ),
                recorder,
            )

    assert run_async.call_count == 1
    assert len(recorder.events) == 2
    assert recorder.events[0] == upstream_event
    assert recorder.events[1].name == "action_v1_short_comparison"
    assert recorder.events[1].status == "blocked"
    assert "embedding preflight pass" in recorder.events[1].reason


def test_preflight_embedding_success_uses_inferred_dimension() -> None:
    with patch(
        "app.memory.evaluation_harness._infer_openai_compatible_embedding_dim",
        return_value=768,
    ):
        from app.memory.evaluation_harness import _preflight_embedding

        event = _preflight_embedding(EvaluationConfig())

    assert event.status == "pass"
    assert event.metrics["embedding_dim"] == 768


def test_build_real_scenario_events_includes_recall_probe_events() -> None:
    class _FakeStore:
        def __init__(self, episodes):
            self.episodes = list(episodes)

        def retrieve_relevant(self, query_text, limit, agent_id=None):
            del query_text
            items = self.episodes
            if agent_id is not None:
                items = [
                    item for item in items
                    if str(item.get("agent_id", "")) == str(agent_id)
                ]
            return list(items[:limit])

    class _FakeObservationPolicy:
        def build_perception_envelope(self, *, prompt_visible_snapshot, observation_prompt):
            if observation_prompt.startswith("No new relevant social content"):
                return SimpleNamespace(
                    topic="",
                    semantic_anchors=[],
                    entities=[],
                    snapshot=prompt_visible_snapshot,
                )
            return SimpleNamespace(
                topic="memory topic",
                semantic_anchors=["post:1"],
                entities=["user:1"],
                snapshot=prompt_visible_snapshot,
            )

    class _FakeRecallPlanner:
        def prepare(
            self,
            *,
            agent_id=None,
            topic="",
            semantic_anchors=None,
            entities=None,
            snapshot=None,
            memory_state=None,
            longterm_store=None,
            next_step_id=0,
            runtime_state=None,
        ):
            del semantic_anchors, entities, snapshot, memory_state, next_step_id, runtime_state
            if not topic:
                return SimpleNamespace(
                    gate_decision=False,
                    retrieval_attempted=False,
                    recalled_count=0,
                    recalled_step_ids=[],
                    query_text="",
                    candidates=[],
                    gate_reason_flags={"topic_trigger": False},
                )
            candidates = list(longterm_store.retrieve_relevant("memory topic", limit=3, agent_id=agent_id))
            return SimpleNamespace(
                gate_decision=True,
                retrieval_attempted=True,
                recalled_count=len(candidates),
                recalled_step_ids=[int(item["step_id"]) for item in candidates],
                query_text="memory topic",
                candidates=candidates,
                gate_reason_flags={"topic_trigger": True},
            )

    episodes = [
        {
            "memory_kind": "action_episode",
            "agent_id": "agent-1",
            "step_id": 3,
            "action_index": 0,
            "action_name": "create_comment",
            "action_fact": "create_comment(content=hello, post_id=1)",
            "topic": "memory topic",
            "query_source": "distilled_topic",
            "target_snapshot": {"summary": "hello there", "post_id": 1},
            "authored_content": "hello there",
            "action_significance": "high",
        },
        {
            "memory_kind": "action_episode",
            "agent_id": "agent-2",
            "step_id": 2,
            "action_index": 0,
            "action_name": "create_post",
            "action_fact": "create_post(content=other)",
            "topic": "other",
            "query_source": "distilled_topic",
            "target_snapshot": {"summary": "other post", "post_id": 2},
            "authored_content": "other post",
            "action_significance": "medium",
        },
    ]

    fake_agent = SimpleNamespace(
        agent_id="agent-1",
        _observation_policy=_FakeObservationPolicy(),
        _recall_planner=_FakeRecallPlanner(),
        _memory_state=object(),
        _persisted_action_episode_ids={(3, 0)},
    )
    manager = SimpleNamespace(
        get_all_agents=lambda: [fake_agent],
        get_state_info=lambda: {"current_step": 3},
        _action_v1_longterm_store=_FakeStore(episodes),
    )
    init_result = {"agent_count": 1}

    events = _build_real_scenario_events(
        manager=manager,
        init_result=init_result,
        config=EvaluationConfig(phases=["real-scenarios"], embedding_url="http://127.0.0.1:11434/v1"),
    )

    event_names = [event.name for event in events]
    assert event_names == [
        "VAL-LTM-05 real_self_action_retrievability",
        "VAL-RCL-08 real_continuity_recall_probe",
        "VAL-RCL-09 real_empty_observation_recall_suppression",
    ]
    assert events[0].status == "pass"
    assert events[1].status == "pass"
    assert events[2].status == "pass"
    assert events[0].metrics["real_probe_candidate_count"] == 2
    assert events[0].metrics["usable_probe_count"] == 2
    assert events[0].metrics["skipped_probe_count"] == 0
    assert events[0].metrics["candidate_action_name_distribution"] == {
        "create_comment": 1,
        "create_post": 1,
    }
    assert events[0].metrics["candidate_agent_distribution"] == {
        "agent-1": 1,
        "agent-2": 1,
    }


def test_build_real_scenario_events_reports_probe_skips() -> None:
    class _FakeStore:
        def retrieve_relevant(self, query_text, limit, agent_id=None):
            del query_text, limit, agent_id
            return [
                {
                    "memory_kind": "action_episode",
                    "agent_id": "agent-1",
                    "step_id": 4,
                    "action_index": 0,
                    "action_name": "like",
                }
            ]

    fake_agent = SimpleNamespace(
        agent_id="agent-1",
        _persisted_action_episode_ids={(4, 0)},
    )
    manager = SimpleNamespace(
        get_all_agents=lambda: [fake_agent],
        get_state_info=lambda: {"current_step": 4},
        _action_v1_longterm_store=_FakeStore(),
    )

    events = _build_real_scenario_events(
        manager=manager,
        init_result={"agent_count": 1},
        config=EvaluationConfig(phases=["real-scenarios"], embedding_url=""),
    )

    event = events[0]
    assert event.status == "fail"
    assert event.metrics["real_probe_candidate_count"] == 1
    assert event.metrics["usable_probe_count"] == 0
    assert event.metrics["skipped_probe_count"] == 1
    assert event.metrics["skipped_probe_reason_counts"] == {"missing_query_text": 1}


def test_build_real_longwindow_events_uses_runtime_snapshots() -> None:
    fake_agent = SimpleNamespace(
        _persisted_action_episode_ids={(3, 0), (6, 0)},
    )
    manager = SimpleNamespace(
        get_all_agents=lambda: [fake_agent],
        get_state_info=lambda: {"current_step": 8},
    )
    init_result = {"agent_count": 1}
    step_snapshots = [
        {
            "step_result": {"step_executed": 7},
            "memory_debug": {
                "agents": [
                    {
                        "agent_id": 1,
                        "user_name": "alice",
                        "last_recall_gate": True,
                        "last_recall_query_text": "remember the earlier post",
                        "last_recalled_count": 2,
                        "last_injected_count": 1,
                        "last_recall_overlap_filtered_count": 0,
                        "last_recall_selection_stop_reason": "",
                        "last_recalled_step_ids": [3, 4],
                        "last_injected_step_ids": [3],
                        "last_prompt_tokens": 1400,
                        "last_observation_stage": "interaction_reduced",
                        "recent_retained_step_count": 3,
                        "compressed_retained_step_count": 5,
                        "total_retained_step_count": 8,
                    }
                ]
            },
        },
        {
            "step_result": {"step_executed": 8},
            "memory_debug": {
                "agents": [
                    {
                        "agent_id": 1,
                        "user_name": "alice",
                        "last_recall_gate": True,
                        "last_recall_query_text": "remember the earlier post",
                        "last_recalled_count": 1,
                        "last_injected_count": 1,
                        "last_recall_overlap_filtered_count": 0,
                        "last_recall_selection_stop_reason": "",
                        "last_recalled_step_ids": [6],
                        "last_injected_step_ids": [6],
                        "last_prompt_tokens": 1600,
                        "last_observation_stage": "raw_fit",
                        "recent_retained_step_count": 3,
                        "compressed_retained_step_count": 6,
                        "total_retained_step_count": 9,
                    }
                ]
            },
        },
    ]

    events = _build_real_longwindow_events(
        manager=manager,
        init_result=init_result,
        config=EvaluationConfig(phases=["real-longwindow"], embedding_url="http://127.0.0.1:11434/v1"),
        step_snapshots=step_snapshots,
    )

    assert [event.name for event in events] == [
        "VAL-RCL-10 real_longwindow_recall_injection"
    ]
    event = events[0]
    assert event.status == "pass"
    assert event.metrics["recall_injected_count"] == 2
    assert event.metrics["recall_injected_trace_count"] == 2
    assert event.metrics["recall_recalled_trace_count"] == 2
    assert event.metrics["recall_recalled_not_injected_trace_count"] == 0
    assert event.metrics["recall_overlap_filtered_count"] == 0
    assert event.metrics["recall_selection_stop_reason_counts"] == {}
    assert event.metrics["used_recall_step_ids"] == [3, 6]
    assert event.metrics["observation_compression_trigger_count"] == 1
    assert event.metrics["avg_prompt_tokens"] == 1500.0
    assert event.metrics["max_prompt_tokens"] == 1600


def test_summarize_comparison_run_for_action_v1_uses_memory_debug_metrics() -> None:
    metrics = _summarize_comparison_run(
        mode=MemoryMode.ACTION_V1,
        init_result={"agent_count": 2},
        manager_step_count=5,
        step_times_ms=[100.0, 200.0],
        step_snapshots=[
            {
                "memory_debug": {
                    "agents": [
                        {
                            "last_recall_gate": True,
                            "last_recalled_count": 1,
                            "last_injected_count": 1,
                            "last_recall_overlap_filtered_count": 0,
                            "last_recall_selection_stop_reason": "",
                            "last_injected_step_ids": [3],
                            "last_prompt_tokens": 1200,
                            "last_observation_stage": "raw_fit",
                            "recent_retained_step_count": 3,
                            "compressed_retained_step_count": 4,
                            "total_retained_step_count": 5,
                        }
                    ]
                }
            }
        ],
        duration_ms=321.0,
        persisted_action_episode_count=7,
    )

    assert metrics["memory_mode"] == "action_v1"
    assert metrics["persisted_action_episode_count"] == 7
    assert metrics["recall_injected_count"] == 1
    assert metrics["shortterm_total_retained_step_count"] == 5


def test_summarize_comparison_run_for_upstream_uses_chat_history_metrics() -> None:
    metrics = _summarize_comparison_run(
        mode=MemoryMode.UPSTREAM,
        init_result={"agent_count": 2},
        manager_step_count=5,
        step_times_ms=[100.0, 200.0],
        step_snapshots=[
            {
                "chat_history": [
                    {
                        "token_truncation_active": True,
                        "window_drop_active": False,
                        "context_token_limit": 16384,
                        "stored_raw_tokens": 20000,
                        "selected_context_tokens": 15000,
                        "stored_record_count": 50,
                        "selected_context_message_count": 20,
                        "token_selection_dropped_record_count": 12,
                        "window_dropped_record_count": 0,
                        "stored_observation_round_count": 6,
                        "selected_observation_round_count": 4,
                    }
                ]
            }
        ],
        duration_ms=321.0,
        persisted_action_episode_count=0,
    )

    assert metrics["memory_mode"] == "upstream"
    assert metrics["chat_history_token_truncation_active_count"] == 1
    assert metrics["max_chat_history_stored_raw_tokens"] == 20000
    assert metrics["peak_chat_history_selected_observation_round_count"] == 4
