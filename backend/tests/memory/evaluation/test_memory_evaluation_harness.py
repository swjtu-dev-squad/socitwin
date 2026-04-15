from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.memory.evaluation_harness import (
    EvaluationConfig,
    EvaluationEvent,
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


def test_preflight_embedding_success_uses_inferred_dimension() -> None:
    with patch(
        "app.memory.evaluation_harness._infer_openai_compatible_embedding_dim",
        return_value=768,
    ):
        from app.memory.evaluation_harness import _preflight_embedding

        event = _preflight_embedding(EvaluationConfig())

    assert event.status == "pass"
    assert event.metrics["embedding_dim"] == 768
