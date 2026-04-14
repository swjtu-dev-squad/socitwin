from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.memory.evaluation_harness import (
    EvaluationConfig,
    build_parser,
    parse_args,
    run_memory_evaluation,
)


def test_run_memory_evaluation_writes_summary_and_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
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
        assert "VAL-OBS-01 long_text_post_fidelity" in event_names
        assert "VAL-RCL-02 strong_signal_recall_trigger" in event_names


def test_parser_accepts_multiple_phases() -> None:
    args = build_parser().parse_args(["--phase", "preflight", "--phase", "deterministic"])
    config = parse_args(["--phase", "preflight", "--phase", "deterministic"])

    assert args.phase == ["preflight", "deterministic"]
    assert config.phases == ["preflight", "deterministic"]
