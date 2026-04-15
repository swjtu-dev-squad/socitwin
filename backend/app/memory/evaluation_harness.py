from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Iterator

from contextlib import contextmanager

from camel.messages import BaseMessage

from app.core.config import get_settings
from app.core.oasis_manager import OASISManager
from app.models.simulation import MemoryMode, PlatformType, SimulationConfig
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
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"
DEFAULT_EMBEDDING_URL = "http://127.0.0.1:11434/v1"


@dataclass(slots=True)
class EvaluationConfig:
    phases: list[str] = field(default_factory=lambda: list(DEFAULT_PHASES))
    output_dir: Path = DEFAULT_OUTPUT_DIR
    run_id: str = ""
    context_token_limit: int = 16384
    generation_max_tokens: int = 1024
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_url: str | None = DEFAULT_EMBEDDING_URL
    embedding_api_key: str | None = None
    smoke_steps: int = 1
    smoke_agent_count: int = 1
    smoke_timeout_seconds: int = 60
    scenario_steps: int = 3
    scenario_agent_count: int = 2
    scenario_timeout_seconds: int = 120


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
        _run_preflight(config, recorder)
    if "deterministic" in config.phases:
        _run_deterministic(config, recorder)
    if "real-smoke" in config.phases:
        _run_real_smoke(config, recorder)
    if "real-scenarios" in config.phases:
        _run_real_scenarios(config, recorder)

    return recorder.finalize(config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Socitwin memory evaluation.")
    parser.add_argument(
        "--phase",
        action="append",
        choices=["preflight", "deterministic", "real-smoke", "real-scenarios"],
        help="Evaluation phases to run.",
    )
    parser.add_argument("--run-id", default="", help="Optional output run id.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for evaluation outputs.",
    )
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="OpenAI-compatible embedding model for preflight/real-smoke.",
    )
    parser.add_argument(
        "--embedding-url",
        default=DEFAULT_EMBEDDING_URL,
        help="OpenAI-compatible embedding base URL.",
    )
    parser.add_argument(
        "--embedding-api-key",
        default="",
        help="Optional embedding API key.",
    )
    parser.add_argument(
        "--smoke-steps",
        type=int,
        default=1,
        help="Number of action_v1 steps for real-smoke.",
    )
    parser.add_argument(
        "--smoke-agent-count",
        type=int,
        default=1,
        help="Number of agents for real-smoke.",
    )
    parser.add_argument(
        "--smoke-timeout-seconds",
        type=int,
        default=60,
        help="Timeout for real-smoke initialize/step flow.",
    )
    parser.add_argument(
        "--scenario-steps",
        type=int,
        default=3,
        help="Number of action_v1 steps for real-scenarios.",
    )
    parser.add_argument(
        "--scenario-agent-count",
        type=int,
        default=2,
        help="Number of agents for real-scenarios.",
    )
    parser.add_argument(
        "--scenario-timeout-seconds",
        type=int,
        default=120,
        help="Timeout for real-scenarios initialize/step flow.",
    )
    return parser


def parse_args(args: list[str] | None = None) -> EvaluationConfig:
    parsed = build_parser().parse_args(args=args)
    return EvaluationConfig(
        phases=parsed.phase or list(DEFAULT_PHASES),
        output_dir=Path(parsed.output_dir),
        run_id=parsed.run_id,
        embedding_model=parsed.embedding_model,
        embedding_url=parsed.embedding_url,
        embedding_api_key=parsed.embedding_api_key or None,
        smoke_steps=parsed.smoke_steps,
        smoke_agent_count=parsed.smoke_agent_count,
        smoke_timeout_seconds=parsed.smoke_timeout_seconds,
        scenario_steps=parsed.scenario_steps,
        scenario_agent_count=parsed.scenario_agent_count,
        scenario_timeout_seconds=parsed.scenario_timeout_seconds,
    )


def _run_preflight(config: EvaluationConfig, recorder: EvaluationRecorder) -> None:
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
    recorder.record(_preflight_embedding(config))


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


def _run_real_smoke(config: EvaluationConfig, recorder: EvaluationRecorder) -> None:
    try:
        metrics = asyncio.run(_run_action_v1_real_smoke_async(config))
        recorder.record(
            EvaluationEvent(
                phase="real-smoke",
                name="action_v1_real_smoke",
                status="pass",
                metrics=metrics,
            )
        )
    except Exception as exc:
        recorder.record(
            EvaluationEvent(
                phase="real-smoke",
                name="action_v1_real_smoke",
                status="blocked",
                reason=str(exc),
            )
        )


def _run_real_scenarios(config: EvaluationConfig, recorder: EvaluationRecorder) -> None:
    try:
        events = asyncio.run(_run_action_v1_real_scenarios_async(config))
        for event in events:
            recorder.record(event)
    except Exception as exc:
        recorder.record(
            EvaluationEvent(
                phase="real-scenarios",
                name="VAL-LTM-05 real_self_action_retrievability",
                status="blocked",
                reason=str(exc),
            )
        )


async def _run_action_v1_real_smoke_async(config: EvaluationConfig) -> dict[str, Any]:
    manager = OASISManager()
    db_dir = Path(tempfile.mkdtemp(prefix="socitwin-real-smoke-"))
    chroma_dir = db_dir / "chroma"
    db_path = db_dir / "simulation.db"
    close_timeout = min(10, max(1, config.smoke_timeout_seconds))

    env_updates = {
        "OASIS_MEMORY_MODE": MemoryMode.ACTION_V1.value,
        "OASIS_CONTEXT_TOKEN_LIMIT": str(config.context_token_limit),
        "OASIS_LONGTERM_ENABLED": "true",
        "OASIS_LONGTERM_CHROMA_PATH": str(chroma_dir),
        "OASIS_LONGTERM_COLLECTION_PREFIX": f"real_smoke_{uuid_suffix()}",
        "OASIS_LONGTERM_EMBEDDING_BACKEND": (
            "openai_compatible" if config.embedding_url else "heuristic"
        ),
        "OASIS_LONGTERM_EMBEDDING_MODEL": config.embedding_model,
        "OASIS_LONGTERM_EMBEDDING_BASE_URL": config.embedding_url or "",
        "OASIS_LONGTERM_EMBEDDING_API_KEY": config.embedding_api_key or "",
    }

    with _temporary_env(env_updates):
        get_settings.cache_clear()
        try:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass
            simulation_config = SimulationConfig(
                platform=PlatformType.REDDIT,
                agent_count=config.smoke_agent_count,
                memory_mode=MemoryMode.ACTION_V1,
                db_path=str(db_path),
                max_steps=max(1, config.smoke_steps),
                agent_source={"source_type": "template"},
            )
            init_result = await asyncio.wait_for(
                manager.initialize(simulation_config),
                timeout=max(1, config.smoke_timeout_seconds),
            )
            for _ in range(max(1, config.smoke_steps)):
                await asyncio.wait_for(
                    manager.step(),
                    timeout=max(1, config.smoke_timeout_seconds),
                )
            debug_info = manager.get_memory_debug_info()
            agents = list(debug_info.get("agents", []) or [])
            return {
                "agent_count": init_result["agent_count"],
                "step_count": debug_info["current_step"],
                "memory_mode": debug_info["memory_mode"],
                "longterm_enabled": debug_info["longterm_enabled"],
                "agent_memory_supported_count": sum(
                    1 for item in agents if item.get("memory_supported")
                ),
                "recent_retained_step_count_max": max(
                    (int(item.get("recent_retained_step_count", 0) or 0) for item in agents),
                    default=0,
                ),
                "compressed_retained_step_count_max": max(
                    (int(item.get("compressed_retained_step_count", 0) or 0) for item in agents),
                    default=0,
                ),
                "recalled_count_max": max(
                    (int(item.get("last_recalled_count", 0) or 0) for item in agents),
                    default=0,
                ),
                "injected_count_max": max(
                    (int(item.get("last_injected_count", 0) or 0) for item in agents),
                    default=0,
                ),
            }
        finally:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass
            get_settings.cache_clear()
            shutil.rmtree(db_dir, ignore_errors=True)


def _preflight_embedding(config: EvaluationConfig) -> EvaluationEvent:
    if not config.embedding_url:
        return EvaluationEvent(
            phase="preflight",
            name="embedding_openai_compatible",
            status="blocked",
            reason="embedding_url is not configured",
        )

    try:
        embedding_dim = _infer_openai_compatible_embedding_dim(
            model=config.embedding_model,
            base_url=config.embedding_url,
            api_key=config.embedding_api_key,
        )
        return EvaluationEvent(
            phase="preflight",
            name="embedding_openai_compatible",
            status="pass",
            metrics={
                "embedding_model": config.embedding_model,
                "embedding_url": config.embedding_url,
                "embedding_dim": embedding_dim,
            },
        )
    except Exception as exc:
        return EvaluationEvent(
            phase="preflight",
            name="embedding_openai_compatible",
            status="blocked",
            metrics={
                "embedding_model": config.embedding_model,
                "embedding_url": config.embedding_url,
            },
            reason=str(exc),
        )


def _infer_openai_compatible_embedding_dim(
    *,
    model: str,
    base_url: str,
    api_key: str | None,
) -> int:
    from openai import OpenAI

    client = OpenAI(
        base_url=base_url,
        api_key=api_key or "EMPTY",
    )
    response = client.embeddings.create(
        model=model,
        input=["socitwin memory evaluation preflight"],
    )
    if not response.data or not response.data[0].embedding:
        raise RuntimeError("embedding response is empty")
    return len(response.data[0].embedding)


async def _run_action_v1_real_scenarios_async(
    config: EvaluationConfig,
) -> list[EvaluationEvent]:
    manager = OASISManager()
    db_dir = Path(tempfile.mkdtemp(prefix="socitwin-real-scenarios-"))
    chroma_dir = db_dir / "chroma"
    db_path = db_dir / "simulation.db"
    close_timeout = min(10, max(1, config.scenario_timeout_seconds))

    env_updates = {
        "OASIS_MEMORY_MODE": MemoryMode.ACTION_V1.value,
        "OASIS_CONTEXT_TOKEN_LIMIT": str(config.context_token_limit),
        "OASIS_LONGTERM_ENABLED": "true",
        "OASIS_LONGTERM_CHROMA_PATH": str(chroma_dir),
        "OASIS_LONGTERM_COLLECTION_PREFIX": f"real_scenarios_{uuid_suffix()}",
        "OASIS_LONGTERM_EMBEDDING_BACKEND": (
            "openai_compatible" if config.embedding_url else "heuristic"
        ),
        "OASIS_LONGTERM_EMBEDDING_MODEL": config.embedding_model,
        "OASIS_LONGTERM_EMBEDDING_BASE_URL": config.embedding_url or "",
        "OASIS_LONGTERM_EMBEDDING_API_KEY": config.embedding_api_key or "",
    }

    with _temporary_env(env_updates):
        get_settings.cache_clear()
        try:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass

            simulation_config = SimulationConfig(
                platform=PlatformType.REDDIT,
                agent_count=config.scenario_agent_count,
                memory_mode=MemoryMode.ACTION_V1,
                db_path=str(db_path),
                max_steps=max(1, config.scenario_steps),
                agent_source={"source_type": "template"},
            )
            init_result = await asyncio.wait_for(
                manager.initialize(simulation_config),
                timeout=max(1, config.scenario_timeout_seconds),
            )
            for _ in range(max(1, config.scenario_steps)):
                await asyncio.wait_for(
                    manager.step(),
                    timeout=max(1, config.scenario_timeout_seconds),
                )

            return _build_real_scenario_events(
                manager=manager,
                init_result=init_result,
                config=config,
            )
        finally:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass
            get_settings.cache_clear()
            shutil.rmtree(db_dir, ignore_errors=True)


def _build_real_scenario_events(
    *,
    manager: OASISManager,
    init_result: dict[str, Any],
    config: EvaluationConfig,
) -> list[EvaluationEvent]:
    agents = list(manager.get_all_agents())
    store = getattr(manager, "_action_v1_longterm_store", None)
    candidates = _collect_real_longterm_probe_candidates(store)
    persisted_count = _count_persisted_action_episodes(agents)
    base_metrics = {
        "memory_mode": MemoryMode.ACTION_V1.value,
        "longterm_backend": (
            "openai_compatible" if config.embedding_url else "heuristic"
        ),
        "agent_count": int(init_result.get("agent_count", len(agents)) or len(agents)),
        "step_count": int(manager.get_state_info().get("current_step", 0) or 0),
        "real_probe_candidate_count": len(candidates),
        "actual_persisted_action_episode_count": persisted_count,
    }
    return [
        _build_real_self_action_retrievability_event(
            agents=agents,
            store=store,
            candidates=candidates,
            base_metrics=base_metrics,
        )
    ]


def _build_real_self_action_retrievability_event(
    *,
    agents: list[Any],
    store: Any,
    candidates: list[dict[str, Any]],
    base_metrics: dict[str, Any],
) -> EvaluationEvent:
    if store is None:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-LTM-05 real_self_action_retrievability",
            status="blocked",
            metrics=base_metrics,
            reason="No long-term store was available for real scenario probe.",
        )
    if not candidates:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-LTM-05 real_self_action_retrievability",
            status="fail",
            metrics=base_metrics,
            reason="No real action episode candidates were retrievable from Chroma.",
        )

    per_query: list[dict[str, Any]] = []
    for candidate in candidates[:5]:
        query_text = _query_from_real_episode(candidate)
        if not query_text:
            continue
        expected_agent_id = str(candidate.get("agent_id", "") or "")
        retrieved = store.retrieve_relevant(
            query_text,
            limit=3,
            agent_id=expected_agent_id or None,
        )
        per_query.append(
            _score_real_episode_retrieval_probe(
                expected=candidate,
                query_text=query_text,
                retrieved=list(retrieved),
            )
        )

    if not per_query:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-LTM-05 real_self_action_retrievability",
            status="fail",
            metrics=base_metrics,
            reason="Real action episodes existed, but no usable probe query could be built.",
        )

    metrics = {
        **base_metrics,
        **_summarize_real_probe_scores(per_query),
        "persisted_action_episode_count": _count_persisted_action_episodes(agents),
    }
    status = "pass" if metrics["hit_at_3"] >= 0.8 else "fail"
    return EvaluationEvent(
        phase="real-scenarios",
        name="VAL-LTM-05 real_self_action_retrievability",
        status=status,
        metrics=metrics,
        evidence={
            "readable_summary": _real_probe_readable_rows(per_query),
            "per_query": per_query,
        },
        reason=(
            ""
            if status == "pass"
            else (
                "real action episode hit@3 below threshold "
                f"(hit_at_3={metrics['hit_at_3']}, threshold=0.8)."
            )
        ),
    )


def _collect_real_longterm_probe_candidates(store: Any) -> list[dict[str, Any]]:
    if store is None:
        return []
    queries = [
        "create_post create_comment authored content state changes",
        "created_post created_comment followed_user sent_group_message",
        "discussion post comment follow group message",
    ]
    by_key: dict[tuple[str, int | None, int | None], dict[str, Any]] = {}
    for query in queries:
        try:
            retrieved = store.retrieve_relevant(query, limit=10)
        except Exception:
            continue
        for item in retrieved:
            if str(item.get("memory_kind", "") or "") != "action_episode":
                continue
            key = _real_episode_key(item)
            if key[1] is None or key[2] is None:
                continue
            by_key[key] = dict(item)
    return sorted(
        by_key.values(),
        key=lambda item: (
            bool(str(item.get("authored_content", "") or "").strip()),
            str(item.get("action_significance", "") or "") == "high",
            int(item.get("step_id", 0) or 0),
        ),
        reverse=True,
    )


def _count_persisted_action_episodes(agents: list[Any]) -> int:
    total = 0
    for agent in agents:
        persisted = getattr(agent, "_persisted_action_episode_ids", None)
        if persisted is not None:
            total += len(persisted)
    return total


def _query_from_real_episode(episode: dict[str, Any]) -> str:
    for key in ("authored_content", "summary_text", "topic", "action_fact"):
        value = str(episode.get(key, "") or "").strip()
        if value:
            return value[:240]
    target_snapshot = episode.get("target_snapshot", {}) or {}
    if isinstance(target_snapshot, dict):
        for key in ("summary", "content", "group_name"):
            value = str(target_snapshot.get(key, "") or "").strip()
            if value:
                return value[:240]
    return ""


def _score_real_episode_retrieval_probe(
    *,
    expected: dict[str, Any],
    query_text: str,
    retrieved: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_key = _real_episode_key(expected)
    retrieved_keys = [_real_episode_key(item) for item in retrieved]
    first_hit_rank = 0
    for index, key in enumerate(retrieved_keys, start=1):
        if key == expected_key:
            first_hit_rank = index
            break
    return {
        "query_text": query_text,
        "expected_key": expected_key,
        "expected_label": _real_episode_label(expected),
        "retrieved_keys": retrieved_keys,
        "retrieved_labels": [_real_episode_label(item) for item in retrieved],
        "retrieved_same_agent_flags": [
            key[0] == expected_key[0] for key in retrieved_keys
        ],
        "cross_agent_retrieved_count": sum(
            1 for key in retrieved_keys[:3] if key[0] != expected_key[0]
        ),
        "first_hit_rank": first_hit_rank,
        "hit_at_1": first_hit_rank == 1,
        "hit_at_3": 0 < first_hit_rank <= 3,
        "recall_at_3": 1.0 if 0 < first_hit_rank <= 3 else 0.0,
        "mrr": round(1 / first_hit_rank, 4) if first_hit_rank else 0.0,
    }


def _summarize_real_probe_scores(per_query: list[dict[str, Any]]) -> dict[str, Any]:
    query_count = len(per_query)
    return {
        "query_count": query_count,
        "hit_at_1": _mean_bool(item["hit_at_1"] for item in per_query),
        "hit_at_3": _mean_bool(item["hit_at_3"] for item in per_query),
        "recall_at_3": round(
            sum(float(item["recall_at_3"]) for item in per_query)
            / max(1, query_count),
            4,
        ),
        "mrr": round(
            sum(float(item["mrr"]) for item in per_query) / max(1, query_count),
            4,
        ),
        "cross_agent_top3_count": sum(
            int(item.get("cross_agent_retrieved_count", 0) or 0)
            for item in per_query
        ),
    }


def _real_probe_readable_rows(per_query: list[dict[str, Any]]) -> list[str]:
    return [
        (
            f"{item['expected_label']}: top={item['retrieved_labels']} "
            f"expected={item['expected_key']} rank={item['first_hit_rank']}"
        )
        for item in per_query
    ]


def _real_episode_key(episode: dict[str, Any]) -> tuple[str, int | None, int | None]:
    agent_id = str(episode.get("agent_id", "") or "")
    step_id = episode.get("step_id")
    action_index = episode.get("action_index")
    return (
        agent_id,
        int(step_id) if step_id is not None else None,
        int(action_index) if action_index is not None else None,
    )


def _real_episode_label(episode: dict[str, Any]) -> str:
    return (
        f"agent={episode.get('agent_id')} "
        f"step={episode.get('step_id')} "
        f"action={episode.get('action_name')}"
    )


def _mean_bool(values: Any) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return round(sum(1.0 if item else 0.0 for item in collected) / len(collected), 4)


def uuid_suffix() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


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


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value == "":
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main(args: list[str] | None = None) -> int:
    config = parse_args(args)
    result = run_memory_evaluation(config)
    print(f"memory evaluation run_dir={result['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
