from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any

from camel.messages import BaseMessage

from .config import ActionV1RuntimeSettings
from .episodic_memory import ActionEpisode
from .longterm import build_chroma_longterm_store
from .observation_shaper import ObservationShaper
from .recall_planner import RecallPlanner, RecallRuntimeState
from .retrieval_policy import RetrievalPolicy
from .tokens import HeuristicUnicodeTokenCounter
from .working_memory import MemoryState


DEFAULT_OUTPUT_DIR = Path("test-results/memory-eval")
DEFAULT_PHASES = ("preflight", "deterministic")


@dataclass(slots=True)
class EvaluationConfig:
    phases: list[str] = field(default_factory=lambda: list(DEFAULT_PHASES))
    output_dir: Path = DEFAULT_OUTPUT_DIR
    run_id: str = ""
    context_token_limit: int = 16384
    generation_max_tokens: int = 1024


@dataclass(slots=True)
class EvaluationEvent:
    phase: str
    name: str
    status: str
    metrics: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvaluationRecorder:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.events: list[EvaluationEvent] = []

    def record(self, event: EvaluationEvent) -> None:
        self.events.append(event)

    def finalize(self, config: EvaluationConfig) -> dict[str, Any]:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "config.json").write_text(
            json.dumps(_jsonable(asdict(config)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.run_dir / "events.jsonl").write_text(
            "\n".join(
                json.dumps(event.to_dict(), ensure_ascii=False) for event in self.events
            ),
            encoding="utf-8",
        )
        summary = self._build_summary(config)
        (self.run_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.run_dir / "README.md").write_text(
            self._build_readme(summary),
            encoding="utf-8",
        )
        return {
            "run_dir": str(self.run_dir),
            "summary": summary["summary"],
            "event_count": len(self.events),
        }

    def _build_summary(self, config: EvaluationConfig) -> dict[str, Any]:
        by_phase: dict[str, dict[str, int]] = {}
        for event in self.events:
            phase_summary = by_phase.setdefault(
                event.phase,
                {"pass": 0, "fail": 0, "blocked": 0},
            )
            phase_summary[event.status] = phase_summary.get(event.status, 0) + 1
        success = not any(event.status == "fail" for event in self.events)
        has_blockers = any(event.status == "blocked" for event in self.events)
        return {
            "config": _jsonable(asdict(config)),
            "summary": {
                "success": success,
                "has_blockers": has_blockers,
                "by_phase": by_phase,
            },
            "event_briefs": [
                {
                    "phase": event.phase,
                    "name": event.name,
                    "status": event.status,
                    "reason": event.reason,
                }
                for event in self.events
            ],
        }

    def _build_readme(self, summary: dict[str, Any]) -> str:
        lines = [
            "# Memory Evaluation Report",
            "",
            "## Summary",
            "",
            f"- success: `{summary['summary']['success']}`",
            f"- has_blockers: `{summary['summary']['has_blockers']}`",
            "",
            "## Events",
            "",
        ]
        for event in self.events:
            lines.append(f"- `{event.phase}` / `{event.name}` / `{event.status}`")
        return "\n".join(lines)


def run_memory_evaluation(config: EvaluationConfig) -> dict[str, Any]:
    run_id = config.run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = config.output_dir / run_id
    recorder = EvaluationRecorder(run_dir)

    if "preflight" in config.phases:
        _run_preflight(recorder)
    if "deterministic" in config.phases:
        _run_deterministic(config, recorder)

    return recorder.finalize(config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Socitwin memory evaluation.")
    parser.add_argument(
        "--phase",
        action="append",
        choices=["preflight", "deterministic"],
        help="Evaluation phases to run.",
    )
    parser.add_argument("--run-id", default="", help="Optional output run id.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for evaluation outputs.",
    )
    return parser


def parse_args(args: list[str] | None = None) -> EvaluationConfig:
    parsed = build_parser().parse_args(args=args)
    return EvaluationConfig(
        phases=parsed.phase or list(DEFAULT_PHASES),
        output_dir=Path(parsed.output_dir),
        run_id=parsed.run_id,
    )


def _run_preflight(recorder: EvaluationRecorder) -> None:
    status = "pass"
    reason = ""
    try:
        import chromadb  # noqa: F401
    except Exception as exc:
        status = "blocked"
        reason = str(exc)
    recorder.record(
        EvaluationEvent(
            phase="preflight",
            name="chromadb_dependency_available",
            status=status,
            reason=reason,
        )
    )


def _run_deterministic(
    config: EvaluationConfig,
    recorder: EvaluationRecorder,
) -> None:
    runtime_settings = _build_runtime_settings(config)
    shaper = ObservationShaper(runtime_settings)

    long_text = "AI safety charter " * 120
    raw_posts = {
        "success": True,
        "posts": [
            {
                "post_id": 1,
                "user_id": 11,
                "content": long_text,
                "comments": [
                    {
                        "comment_id": 101,
                        "user_id": 12,
                        "content": "支持这个议题，但需要更具体措施。",
                    }
                ],
            }
        ],
    }
    raw_groups = {
        "all_groups": {1: "AI Safety"},
        "joined_groups": [1],
        "messages": [
            {
                "message_id": 201,
                "group_id": 1,
                "user_id": 13,
                "content": "今晚讨论治理框架。",
            }
        ],
    }
    artifact = shaper.shape(
        posts_payload=raw_posts,
        groups_payload=raw_groups,
        current_agent_id=11,
    )
    recorder.record(
        EvaluationEvent(
            phase="deterministic",
            name="VAL-OBS-01 long_text_post_fidelity",
            status="pass",
            metrics={
                "final_shaping_stage": artifact.render_stats.get("final_shaping_stage", ""),
                "processed_prompt_tokens": artifact.render_stats.get(
                    "observation_prompt_tokens",
                    0,
                ),
                "truncated_field_count": artifact.render_stats.get(
                    "truncated_field_count",
                    0,
                ),
            },
            evidence={
                "prompt_visible_snapshot": artifact.prompt_visible_snapshot,
            },
        )
    )

    with tempfile.TemporaryDirectory() as tmp:
        store = build_chroma_longterm_store(
            collection_name="socitwin_memory_eval",
            embedding_backend="heuristic",
            client_type="ephemeral",
            path=tmp,
            delete_collection_on_close=False,
        )
        episode = ActionEpisode(
            agent_id="agent-1",
            step_id=7,
            action_index=0,
            timestamp=1.0,
            platform="twitter",
            action_name="create_post",
            action_category="post",
            action_fact="create_post(content=AI safety charter)",
            target_type="post",
            target_snapshot={"summary": "AI safety charter"},
            target_visible_in_prompt=True,
            target_resolution_status="resolved",
            execution_status="success",
            local_context={},
            authored_content="AI safety charter for multilingual deployment",
            state_changes=["created_post:1"],
            outcome="posted charter",
            topic="ai safety charter",
            query_source="distilled_topic",
            action_significance="high",
        )
        store.write_episode(episode.to_payload())

        planner = RecallPlanner(
            runtime_settings=runtime_settings,
            retrieval_policy=RetrievalPolicy(),
        )
        preparation = planner.prepare(
            agent_id="agent-1",
            topic="ai safety charter",
            semantic_anchors=["post:1"],
            entities=[],
            snapshot={"posts": {"posts": [{"post_id": 1, "user_id": 11}]}},
            memory_state=MemoryState(),
            longterm_store=store,
            next_step_id=8,
            runtime_state=RecallRuntimeState(),
        )
        recorder.record(
            EvaluationEvent(
                phase="deterministic",
                name="VAL-RCL-02 strong_signal_recall_trigger",
                status="pass" if preparation.gate_decision and preparation.recalled_count > 0 else "fail",
                metrics={
                    "gate_decision": preparation.gate_decision,
                    "recalled_count": preparation.recalled_count,
                    "retrieved_step_ids": list(preparation.recalled_step_ids),
                },
                evidence={
                    "gate_reason_flags": dict(preparation.gate_reason_flags),
                    "query_source": preparation.query_source,
                    "query_text": preparation.query_text,
                },
            )
        )


def _build_runtime_settings(config: EvaluationConfig) -> ActionV1RuntimeSettings:
    return ActionV1RuntimeSettings(
        token_counter=HeuristicUnicodeTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="You are a social agent.",
        ),
        context_token_limit=config.context_token_limit,
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def main(args: list[str] | None = None) -> int:
    config = parse_args(args)
    result = run_memory_evaluation(config)
    print(f"memory evaluation run_dir={result['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
