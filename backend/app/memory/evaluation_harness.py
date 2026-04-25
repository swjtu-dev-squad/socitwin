from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import tempfile
import time
import warnings
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from camel.memories import MemoryRecord
from camel.messages import BaseMessage
from oasis import ActionType, ManualAction

from app.core.config import get_settings
from app.core.oasis_manager import OASISManager
from app.models.simulation import AgentSource, MemoryMode, PlatformType, SimulationConfig

from .config import ActionV1RuntimeSettings
from .episodic_memory import ActionEpisode
from .longterm import build_chroma_longterm_store, payload_to_episode
from .observation_shaper import ObservationShaper
from .recall_planner import RecallPlanner, RecallRuntimeState
from .retrieval_policy import RetrievalPolicy
from .tokens import HeuristicUnicodeTokenCounter
from .working_memory import MemoryState

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = BACKEND_ROOT / "test-results" / "memory-eval"
DEFAULT_B_LEVEL_FIXTURE_PATH = (
    BACKEND_ROOT / "tests" / "memory" / "evaluation" / "fixtures" / "b_level_real_run_packs.json"
)
DEFAULT_PHASES = ("preflight", "deterministic")
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"
DEFAULT_EMBEDDING_URL = "http://127.0.0.1:11434/v1"
DEFAULT_SCENARIO_PROBE_LIMIT = 25
MEMORY_KPI_FIELDS = (
    "ltm_exact_hit_at_1",
    "ltm_exact_hit_at_3",
    "ltm_mrr",
    "cross_agent_contamination_rate",
    "recall_gate_success_rate",
    "false_recall_trigger_rate",
    "recall_injection_trace_rate",
)
MEMORY_KPI_SOURCES = {
    "ltm_exact_hit_at_1": ["VAL-LTM-05 real_self_action_retrievability"],
    "ltm_exact_hit_at_3": ["VAL-LTM-05 real_self_action_retrievability"],
    "ltm_mrr": ["VAL-LTM-05 real_self_action_retrievability"],
    "cross_agent_contamination_rate": ["VAL-LTM-05 real_self_action_retrievability"],
    "recall_gate_success_rate": ["VAL-RCL-08 real_continuity_recall_probe"],
    "false_recall_trigger_rate": [
        "VAL-RCL-09 real_empty_observation_recall_suppression"
    ],
    "recall_injection_trace_rate": ["VAL-RCL-10 real_longwindow_recall_injection"],
}


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
    scenario_probe_limit: int = DEFAULT_SCENARIO_PROBE_LIMIT
    scenario_pack: str = ""
    scenario_fixture_path: Path = DEFAULT_B_LEVEL_FIXTURE_PATH
    longwindow_steps: int = 8
    longwindow_agent_count: int = 2
    longwindow_timeout_seconds: int = 240
    comparison_steps: int = 5
    comparison_agent_count: int = 2
    comparison_timeout_seconds: int = 240


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
        memory_kpis, unavailable_metrics = _build_memory_kpis(self.events)
        return {
            "config": _jsonable(asdict(config)),
            "summary": {
                "success": success,
                "has_blockers": has_blockers,
                "by_phase": by_phase,
            },
            "memory_kpis": memory_kpis,
            "memory_kpi_sources": MEMORY_KPI_SOURCES,
            "unavailable_metrics": unavailable_metrics,
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
            "# 记忆评测报告",
            "",
            "## 1. 运行结论",
            "",
            f"- 总体是否通过：`{_zh_bool(summary['summary']['success'])}`",
            f"- 是否存在阻塞项：`{_zh_bool(summary['summary']['has_blockers'])}`",
            f"- 运行目录：`{self.run_dir}`",
            "",
        ]
        lines.extend(_memory_kpi_readme_lines(summary))
        lines.extend(_real_scenario_readme_lines(self.events))
        lines.extend(_recall_probe_readme_lines(self.events))
        lines.extend(["", "## 8. 事件列表", ""])
        for event in self.events:
            reason = f"；原因：{event.reason}" if event.reason else ""
            lines.append(
                f"- `{event.phase}` / `{event.name}` / `{_zh_status(event.status)}`{reason}"
            )
        lines.extend(
            [
                "",
                "## 9. 原始文件说明",
                "",
                "- `summary.json`：机器可读的总览、KPI 和不可用指标。",
                "- `events.jsonl`：逐事件详细证据；检索类事件包含逐条 probe 的 expected / retrieved 信息。",
                "- `config.json`：本次评测参数，包括场景、步数、probe limit 和 embedding 配置。",
                "- `README.md`：当前中文摘要报告，面向人工阅读和组会复盘。",
            ]
        )
        return "\n".join(lines)


def _build_memory_kpis(
    events: list[EvaluationEvent],
) -> tuple[dict[str, float | None], list[dict[str, str]]]:
    kpis: dict[str, float | None] = {field: None for field in MEMORY_KPI_FIELDS}
    unavailable: list[dict[str, str]] = []

    ltm_event = _first_event(events, "VAL-LTM-05 real_self_action_retrievability")
    if _event_has_metric(ltm_event, "hit_at_3"):
        metrics = ltm_event.metrics if ltm_event else {}
        kpis["ltm_exact_hit_at_1"] = _optional_float(metrics.get("hit_at_1"))
        kpis["ltm_exact_hit_at_3"] = _optional_float(metrics.get("hit_at_3"))
        kpis["ltm_mrr"] = _optional_float(metrics.get("mrr"))
        top3_slots = int(metrics.get("top3_candidate_slot_count", 0) or 0)
        cross_agent_count = int(metrics.get("cross_agent_top3_count", 0) or 0)
        if top3_slots > 0:
            kpis["cross_agent_contamination_rate"] = round(
                cross_agent_count / top3_slots,
                4,
            )
        else:
            _mark_unavailable(
                unavailable,
                "cross_agent_contamination_rate",
                "top3_candidate_slot_count is missing or zero",
            )
    else:
        reason = _unavailable_event_reason(ltm_event)
        for metric in (
            "ltm_exact_hit_at_1",
            "ltm_exact_hit_at_3",
            "ltm_mrr",
            "cross_agent_contamination_rate",
        ):
            _mark_unavailable(unavailable, metric, reason)

    gate_event = _first_event(events, "VAL-RCL-08 real_continuity_recall_probe")
    if _event_has_metric(gate_event, "gate_decision"):
        assert gate_event is not None
        kpis["recall_gate_success_rate"] = (
            1.0 if bool(gate_event.metrics.get("gate_decision")) else 0.0
        )
    else:
        _mark_unavailable(
            unavailable,
            "recall_gate_success_rate",
            _unavailable_event_reason(gate_event),
        )

    suppression_event = _first_event(
        events,
        "VAL-RCL-09 real_empty_observation_recall_suppression",
    )
    if _event_has_metric(suppression_event, "gate_decision"):
        assert suppression_event is not None
        false_triggered = (
            bool(suppression_event.metrics.get("gate_decision"))
            or bool(suppression_event.metrics.get("retrieval_attempted"))
            or int(suppression_event.metrics.get("recalled_count", 0) or 0) > 0
        )
        kpis["false_recall_trigger_rate"] = 1.0 if false_triggered else 0.0
    else:
        _mark_unavailable(
            unavailable,
            "false_recall_trigger_rate",
            _unavailable_event_reason(suppression_event),
        )

    injection_event = _first_event(events, "VAL-RCL-10 real_longwindow_recall_injection")
    if _event_has_metric(injection_event, "recall_recalled_trace_count"):
        assert injection_event is not None
        recalled_trace_count = int(
            injection_event.metrics.get("recall_recalled_trace_count", 0) or 0
        )
        injected_trace_count = int(
            injection_event.metrics.get("recall_injected_trace_count", 0) or 0
        )
        if recalled_trace_count > 0:
            kpis["recall_injection_trace_rate"] = round(
                injected_trace_count / recalled_trace_count,
                4,
            )
        else:
            _mark_unavailable(
                unavailable,
                "recall_injection_trace_rate",
                "recall_recalled_trace_count is zero",
            )
    else:
        _mark_unavailable(
            unavailable,
            "recall_injection_trace_rate",
            _unavailable_event_reason(injection_event),
        )

    return kpis, unavailable


def _first_event(
    events: list[EvaluationEvent],
    name: str,
) -> EvaluationEvent | None:
    for event in events:
        if event.name == name:
            return event
    return None


def _event_has_metric(event: EvaluationEvent | None, metric: str) -> bool:
    return event is not None and event.status != "blocked" and metric in event.metrics


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _mark_unavailable(
    unavailable: list[dict[str, str]],
    metric: str,
    reason: str,
) -> None:
    unavailable.append(
        {
            "metric": metric,
            "reason": reason,
            "required_event": ", ".join(MEMORY_KPI_SOURCES.get(metric, [])),
            "required_metric": _required_metric_for_memory_kpi(metric),
        }
    )


def _unavailable_event_reason(event: EvaluationEvent | None) -> str:
    if event is None:
        return "required evaluation event was not produced"
    if event.status == "blocked":
        return event.reason or "required evaluation event was blocked"
    return "required metric was not produced by evaluation event"


def _required_metric_for_memory_kpi(metric: str) -> str:
    mapping = {
        "ltm_exact_hit_at_1": "hit_at_1",
        "ltm_exact_hit_at_3": "hit_at_3",
        "ltm_mrr": "mrr",
        "cross_agent_contamination_rate": (
            "cross_agent_top3_count + top3_candidate_slot_count"
        ),
        "recall_gate_success_rate": "gate_decision",
        "false_recall_trigger_rate": (
            "gate_decision + retrieval_attempted + recalled_count"
        ),
        "recall_injection_trace_rate": (
            "recall_injected_trace_count + recall_recalled_trace_count"
        ),
    }
    return mapping.get(metric, "")


def _zh_bool(value: Any) -> str:
    return "是" if bool(value) else "否"


def _zh_status(status: str) -> str:
    return {
        "pass": "通过",
        "fail": "失败",
        "blocked": "阻塞",
    }.get(status, status)


def _memory_kpi_readme_lines(summary: dict[str, Any]) -> list[str]:
    lines = [
        "## 2. 核心指标",
        "",
        "| 指标 | 数值 | 怎么理解 |",
        "| --- | ---: | --- |",
    ]
    kpis = summary.get("memory_kpis", {})
    for kpi_field, description in _memory_kpi_descriptions().items():
        value = kpis.get(kpi_field)
        rendered = "n/a" if value is None else str(value)
        lines.append(f"| `{kpi_field}` | `{rendered}` | {description} |")
    lines.extend(
        [
            "",
            "说明：",
            "",
            "- `ltm_exact_hit_at_3` 可以对外解释为 LTM Retrieval Recall@3，但这里是单目标 exact episode hit，不是传统多相关文档 Recall@K。",
            "- 当前 ground truth 是精确的 `(agent_id, step_id, action_index)`，所以同一步另一个动作被召回也不算 exact hit。",
            "- `recall_injection_trace_rate` 是 trace 级注入痕迹，能说明记忆进入 prompt，但不能证明模型最终行为一定使用了该记忆。",
            "- `real-scenarios` 中的 `VAL-RCL-08/09` 是 retrieve-only probe，只验证 gate + retrieval，不执行完整 prompt assembly。",
        ]
    )
    unavailable = list(summary.get("unavailable_metrics", []) or [])
    if unavailable:
        lines.extend(["", "## 3. 不可用指标", ""])
        for item in unavailable:
            lines.append(
                "- "
                f"`{item.get('metric', '')}`：{item.get('reason', '')}；"
                f"需要事件 `{item.get('required_event', '')}`，"
                f"需要字段 `{item.get('required_metric', '')}`。"
            )
    return lines


def _memory_kpi_descriptions() -> dict[str, str]:
    return {
        "ltm_exact_hit_at_1": "目标历史动作是否排在 top-1；越高说明排序越尖锐。",
        "ltm_exact_hit_at_3": "目标历史动作是否进入 top-3；当前主检索召回指标。",
        "ltm_mrr": "目标首次命中的倒数排名均值；越高说明目标越靠前。",
        "cross_agent_contamination_rate": "top-3 中错误 agent 的比例；正常应接近 0。",
        "recall_gate_success_rate": "正例 recall probe 中 gate 是否打开。",
        "false_recall_trigger_rate": "空/弱 observation 下是否误触发 recall；越低越好。",
        "recall_injection_trace_rate": "长窗口运行中 recalled 记忆进入 prompt 的 trace 比例。",
    }


def _real_scenario_readme_lines(events: list[EvaluationEvent]) -> list[str]:
    event = _first_event(events, "VAL-LTM-05 real_self_action_retrievability")
    if event is None:
        return []
    metrics = event.metrics
    lines = [
        "",
        "## 4. Real-Scenarios 样本覆盖",
        "",
        f"- 场景包：`{metrics.get('scenario_pack_id', '') or '未指定'}`",
        f"- 场景目的：{metrics.get('scenario_pack_purpose', '') or '未记录'}",
        f"- 运行步数：`{metrics.get('step_count', 0)}`",
        f"- 实际持久化 ActionEpisode 数：`{metrics.get('actual_persisted_action_episode_count', 0)}`",
        f"- 原始可回查候选数：`{metrics.get('raw_real_probe_candidate_count', 0)}`",
        f"- warm-up 排除候选数：`{metrics.get('warmup_excluded_probe_candidate_count', 0)}`",
        f"- probe limit：`{metrics.get('probe_attempt_limit', 0)}`",
        f"- 实际可用 probe 数：`{metrics.get('usable_probe_count', 0)}`",
        f"- 跳过 probe 数：`{metrics.get('skipped_probe_count', 0)}`",
        f"- 跳过原因：`{json.dumps(metrics.get('skipped_probe_reason_counts', {}), ensure_ascii=False)}`",
        "",
        "动作分布：",
        "",
        f"- 候选池：`{json.dumps(metrics.get('candidate_action_name_distribution', {}), ensure_ascii=False)}`",
        f"- 实际出题：`{json.dumps(metrics.get('usable_probe_action_name_distribution', {}), ensure_ascii=False)}`",
    ]
    action_rows = _action_score_rows(event)
    if action_rows:
        lines.extend(
            [
                "",
                "## 5. 按动作类型的检索表现",
                "",
                "| 动作 | probe 数 | Hit@1 | Hit@3 | MRR | Miss 数 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in action_rows:
            lines.append(
                f"| `{row['action_name']}` | {row['query_count']} | "
                f"{row['hit_at_1']} | {row['hit_at_3']} | {row['mrr']} | {row['miss_count']} |"
            )
    miss_lines = _miss_case_readme_lines(event)
    if miss_lines:
        lines.extend(miss_lines)
    return lines


def _action_score_rows(event: EvaluationEvent) -> list[dict[str, Any]]:
    per_query = list(event.evidence.get("per_query", []) or [])
    return _probe_score_rows_by_action(per_query)


def _miss_case_readme_lines(event: EvaluationEvent, *, limit: int = 8) -> list[str]:
    per_query = list(event.evidence.get("per_query", []) or [])
    misses = [item for item in per_query if not item.get("hit_at_3")]
    if not misses:
        return [
            "",
            "## 6. 未命中样例",
            "",
            "- 本次没有 top-3 未命中的 probe。",
        ]
    lines = [
        "",
        "## 6. 未命中样例",
        "",
        f"以下最多展示前 {limit} 个 top-3 未命中 probe。完整列表见 `events.jsonl` 的 `VAL-LTM-05.evidence.per_query`。",
        "",
    ]
    for index, item in enumerate(misses[:limit], start=1):
        retrieved_labels = item.get("retrieved_labels", []) or []
        same_agent_flags = item.get("retrieved_same_agent_flags", []) or []
        query_text = _truncate_text(str(item.get("query_text", "") or ""), 180)
        lines.extend(
            [
                f"{index}. 期望：`{item.get('expected_label', '')}`",
                f"   - 查询文本：{query_text}",
                f"   - top-3：`{json.dumps(retrieved_labels[:3], ensure_ascii=False)}`",
                f"   - 是否同 agent：`{json.dumps(same_agent_flags[:3], ensure_ascii=False)}`",
                f"   - 首次命中排名：`{item.get('first_hit_rank', 0) or '未命中'}`",
                "",
            ]
        )
    return lines


def _recall_probe_readme_lines(events: list[EvaluationEvent]) -> list[str]:
    lines = ["", "## 7. Recall Gate / Suppression", ""]
    has_any = False
    for name in (
        "VAL-RCL-08 real_continuity_recall_probe",
        "VAL-RCL-09 real_empty_observation_recall_suppression",
        "VAL-RCL-10 real_longwindow_recall_injection",
    ):
        event = _first_event(events, name)
        if event is None:
            continue
        has_any = True
        metrics = event.metrics
        lines.append(f"- `{name}`：`{_zh_status(event.status)}`")
        if "gate_decision" in metrics:
            lines.append(f"  - gate_decision：`{_zh_bool(metrics.get('gate_decision'))}`")
        if "retrieval_attempted" in metrics:
            lines.append(
                f"  - retrieval_attempted：`{_zh_bool(metrics.get('retrieval_attempted'))}`"
            )
        if "recalled_count" in metrics:
            lines.append(f"  - recalled_count：`{metrics.get('recalled_count')}`")
        if "injected_count" in metrics:
            lines.append(f"  - injected_count：`{metrics.get('injected_count')}`")
        if event.reason:
            lines.append(f"  - 原因：{event.reason}")
    return lines if has_any else []


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


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
    if "real-longwindow" in config.phases:
        _run_real_longwindow(config, recorder)
    if "comparison" in config.phases:
        _run_comparison(config, recorder)

    return recorder.finalize(config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Socitwin memory evaluation.")
    parser.add_argument(
        "--phase",
        action="append",
        choices=[
            "preflight",
            "deterministic",
            "real-smoke",
            "real-scenarios",
            "real-longwindow",
            "comparison",
        ],
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
    parser.add_argument(
        "--scenario-probe-limit",
        type=int,
        default=DEFAULT_SCENARIO_PROBE_LIMIT,
        help=(
            "Maximum real-scenarios probe candidates to score. "
            f"Default is {DEFAULT_SCENARIO_PROBE_LIMIT}."
        ),
    )
    parser.add_argument(
        "--scenario-pack",
        default="",
        help=(
            "Optional B-level fixture pack id for real-scenarios "
            "(for example s1_stable_single_topic)."
        ),
    )
    parser.add_argument(
        "--scenario-fixture-path",
        default=str(DEFAULT_B_LEVEL_FIXTURE_PATH),
        help="Path to B-level real-run fixture packs JSON.",
    )
    parser.add_argument(
        "--longwindow-steps",
        type=int,
        default=8,
        help="Number of action_v1 steps for real-longwindow.",
    )
    parser.add_argument(
        "--longwindow-agent-count",
        type=int,
        default=2,
        help="Number of agents for real-longwindow.",
    )
    parser.add_argument(
        "--longwindow-timeout-seconds",
        type=int,
        default=240,
        help="Timeout for real-longwindow initialize/step flow.",
    )
    parser.add_argument(
        "--comparison-steps",
        type=int,
        default=5,
        help="Number of steps for two-mode comparison.",
    )
    parser.add_argument(
        "--comparison-agent-count",
        type=int,
        default=2,
        help="Number of agents for two-mode comparison.",
    )
    parser.add_argument(
        "--comparison-timeout-seconds",
        type=int,
        default=240,
        help="Timeout for two-mode comparison initialize/step flow.",
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
        scenario_probe_limit=parsed.scenario_probe_limit,
        scenario_pack=parsed.scenario_pack,
        scenario_fixture_path=Path(parsed.scenario_fixture_path),
        longwindow_steps=parsed.longwindow_steps,
        longwindow_agent_count=parsed.longwindow_agent_count,
        longwindow_timeout_seconds=parsed.longwindow_timeout_seconds,
        comparison_steps=parsed.comparison_steps,
        comparison_agent_count=parsed.comparison_agent_count,
        comparison_timeout_seconds=parsed.comparison_timeout_seconds,
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
        store.write_episode(payload_to_episode(episode.to_payload()))

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


def _run_real_longwindow(config: EvaluationConfig, recorder: EvaluationRecorder) -> None:
    try:
        events = asyncio.run(_run_action_v1_real_longwindow_async(config))
        for event in events:
            recorder.record(event)
    except Exception as exc:
        recorder.record(
            EvaluationEvent(
                phase="real-longwindow",
                name="VAL-RCL-10 real_longwindow_recall_injection",
                status="blocked",
                reason=str(exc),
            )
        )


def _run_comparison(config: EvaluationConfig, recorder: EvaluationRecorder) -> None:
    for mode in (MemoryMode.UPSTREAM, MemoryMode.ACTION_V1):
        blocker = _comparison_embedding_blocker(config=config, mode=mode)
        if blocker is not None:
            recorder.record(blocker)
            continue
        try:
            event = asyncio.run(_run_mode_comparison_async(config=config, mode=mode))
        except Exception as exc:
            event = EvaluationEvent(
                phase="comparison",
                name=f"{mode.value}_short_comparison",
                status="blocked",
                metrics={"memory_mode": mode.value},
                reason=str(exc),
            )
        recorder.record(event)


def _comparison_embedding_blocker(
    *,
    config: EvaluationConfig,
    mode: MemoryMode,
) -> EvaluationEvent | None:
    if mode != MemoryMode.ACTION_V1:
        return None
    embedding_event = _preflight_embedding(config)
    if embedding_event.status == "pass":
        return None
    metrics = {
        "memory_mode": mode.value,
        **dict(embedding_event.metrics or {}),
    }
    return EvaluationEvent(
        phase="comparison",
        name=f"{mode.value}_short_comparison",
        status="blocked",
        metrics=metrics,
        reason=(
            "comparison for action_v1 requires embedding preflight pass: "
            f"{embedding_event.reason or 'embedding preflight blocked'}"
        ),
    )


def _load_b_level_scenario_pack(config: EvaluationConfig) -> dict[str, Any]:
    fixture_path = Path(config.scenario_fixture_path)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    packs = payload.get("packs", [])
    if not isinstance(packs, list):
        raise ValueError(f"B-level fixture file has invalid packs list: {fixture_path}")
    for item in packs:
        if not isinstance(item, dict):
            continue
        if str(item.get("id", "") or "") == config.scenario_pack:
            _validate_b_level_scenario_pack(item)
            return item
    raise ValueError(
        f"B-level scenario pack not found: {config.scenario_pack} "
        f"in {fixture_path}"
    )


def _validate_b_level_scenario_pack(pack: dict[str, Any]) -> None:
    agents = pack.get("agents", [])
    seed_post = pack.get("seed_post", {})
    if not isinstance(agents, list) or not agents:
        raise ValueError(f"B-level scenario pack has no agents: {pack.get('id')}")
    if not isinstance(seed_post, dict) or not str(seed_post.get("content", "")).strip():
        raise ValueError(f"B-level scenario pack has no seed post: {pack.get('id')}")
    agent_ids = {
        int(agent["agent_id"])
        for agent in agents
        if isinstance(agent, dict) and "agent_id" in agent
    }
    seed_author_id = int(seed_post.get("author_agent_id", 0))
    if seed_author_id not in agent_ids:
        raise ValueError(
            f"B-level scenario pack seed author {seed_author_id} is not in agents: "
            f"{pack.get('id')}"
        )


def _scenario_pack_platform(scenario_pack: dict[str, Any] | None) -> PlatformType:
    if not scenario_pack:
        return PlatformType.REDDIT
    return PlatformType(str(scenario_pack.get("platform", "twitter") or "twitter"))


def _scenario_pack_agent_source(
    scenario_pack: dict[str, Any] | None,
) -> AgentSource:
    if not scenario_pack:
        return AgentSource(source_type="template")
    return AgentSource(
        source_type="manual",
        manual_config=list(scenario_pack.get("agents", []) or []),
    )


async def _run_b_level_pack_warmup(
    *,
    manager: OASISManager,
    scenario_pack: dict[str, Any],
    timeout_seconds: int,
) -> None:
    seed_post = dict(scenario_pack.get("seed_post", {}) or {})
    author_agent_id = int(seed_post.get("author_agent_id", 0))
    content = str(seed_post.get("content", "") or "").strip()
    author_agent = manager.get_agent(author_agent_id)
    if author_agent is None:
        raise ValueError(
            f"Seed author agent not found for scenario pack {scenario_pack.get('id')}: "
            f"{author_agent_id}"
        )
    await asyncio.wait_for(
        manager.step(
            {
                author_agent: ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": content},
                )
            },
            count_towards_budget=False,
        ),
        timeout=timeout_seconds,
    )
    refresh_actions: dict[Any, Any] = {
        agent: ManualAction(action_type=ActionType.REFRESH, action_args={})
        for agent in manager.get_all_agents()
    }
    if refresh_actions:
        await asyncio.wait_for(
            manager.step(refresh_actions, count_towards_budget=False),
            timeout=timeout_seconds,
        )


def _collect_persisted_action_episode_keys(
    agents: list[Any],
) -> set[tuple[str, int | None, int | None]]:
    keys: set[tuple[str, int | None, int | None]] = set()
    for agent in agents:
        agent_id = str(getattr(agent, "agent_id", "") or "")
        persisted = getattr(agent, "_persisted_action_episode_ids", None) or set()
        for item in persisted:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            step_id, action_index = item
            keys.add(
                (
                    agent_id,
                    int(step_id) if step_id is not None else None,
                    int(action_index) if action_index is not None else None,
                )
            )
    return keys


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
                agent_source=AgentSource(source_type="template"),
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
    scenario_pack = _load_b_level_scenario_pack(config) if config.scenario_pack else None
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
                platform=_scenario_pack_platform(scenario_pack),
                agent_count=(
                    len(scenario_pack["agents"])
                    if scenario_pack
                    else config.scenario_agent_count
                ),
                memory_mode=MemoryMode.ACTION_V1,
                db_path=str(db_path),
                max_steps=max(1, config.scenario_steps),
                agent_source=_scenario_pack_agent_source(scenario_pack),
            )
            init_result = await asyncio.wait_for(
                manager.initialize(simulation_config),
                timeout=max(1, config.scenario_timeout_seconds),
            )
            warmup_episode_keys: set[tuple[str, int | None, int | None]] = set()
            if scenario_pack:
                await _run_b_level_pack_warmup(
                    manager=manager,
                    scenario_pack=scenario_pack,
                    timeout_seconds=max(1, config.scenario_timeout_seconds),
                )
                warmup_episode_keys = _collect_persisted_action_episode_keys(
                    list(manager.get_all_agents())
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
                scenario_pack=scenario_pack,
                excluded_episode_keys=warmup_episode_keys,
            )
        finally:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass
            get_settings.cache_clear()
            shutil.rmtree(db_dir, ignore_errors=True)


async def _run_action_v1_real_longwindow_async(
    config: EvaluationConfig,
) -> list[EvaluationEvent]:
    manager = OASISManager()
    db_dir = Path(tempfile.mkdtemp(prefix="socitwin-real-longwindow-"))
    chroma_dir = db_dir / "chroma"
    db_path = db_dir / "simulation.db"
    close_timeout = min(10, max(1, config.longwindow_timeout_seconds))

    env_updates = {
        "OASIS_MEMORY_MODE": MemoryMode.ACTION_V1.value,
        "OASIS_CONTEXT_TOKEN_LIMIT": str(config.context_token_limit),
        "OASIS_LONGTERM_ENABLED": "true",
        "OASIS_LONGTERM_CHROMA_PATH": str(chroma_dir),
        "OASIS_LONGTERM_COLLECTION_PREFIX": f"real_longwindow_{uuid_suffix()}",
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
                agent_count=config.longwindow_agent_count,
                memory_mode=MemoryMode.ACTION_V1,
                db_path=str(db_path),
                max_steps=max(1, config.longwindow_steps),
                agent_source=AgentSource(source_type="template"),
            )
            init_result = await asyncio.wait_for(
                manager.initialize(simulation_config),
                timeout=max(1, config.longwindow_timeout_seconds),
            )
            step_snapshots: list[dict[str, Any]] = []
            for _ in range(max(1, config.longwindow_steps)):
                step_result = await asyncio.wait_for(
                    manager.step(),
                    timeout=max(1, config.longwindow_timeout_seconds),
                )
                step_snapshots.append(
                    {
                        "step_result": dict(step_result or {}),
                        "memory_debug": manager.get_memory_debug_info(),
                    }
                )

            return _build_real_longwindow_events(
                manager=manager,
                init_result=init_result,
                config=config,
                step_snapshots=step_snapshots,
            )
        finally:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass
            get_settings.cache_clear()
            shutil.rmtree(db_dir, ignore_errors=True)


async def _run_mode_comparison_async(
    *,
    config: EvaluationConfig,
    mode: MemoryMode,
) -> EvaluationEvent:
    manager = OASISManager()
    db_dir = Path(tempfile.mkdtemp(prefix=f"socitwin-comparison-{mode.value}-"))
    chroma_dir = db_dir / "chroma"
    db_path = db_dir / "simulation.db"
    close_timeout = min(10, max(1, config.comparison_timeout_seconds))
    longterm_enabled = mode == MemoryMode.ACTION_V1
    env_updates = {
        "OASIS_MEMORY_MODE": mode.value,
        "OASIS_CONTEXT_TOKEN_LIMIT": str(config.context_token_limit),
        "OASIS_LONGTERM_ENABLED": "true" if longterm_enabled else "false",
        "OASIS_LONGTERM_CHROMA_PATH": str(chroma_dir),
        "OASIS_LONGTERM_COLLECTION_PREFIX": f"comparison_{mode.value}_{uuid_suffix()}",
        "OASIS_LONGTERM_EMBEDDING_BACKEND": (
            "openai_compatible" if config.embedding_url else "heuristic"
        ),
        "OASIS_LONGTERM_EMBEDDING_MODEL": config.embedding_model,
        "OASIS_LONGTERM_EMBEDDING_BASE_URL": config.embedding_url or "",
        "OASIS_LONGTERM_EMBEDDING_API_KEY": config.embedding_api_key or "",
    }

    step_snapshots: list[dict[str, Any]] = []
    step_times_ms: list[float] = []
    persisted_action_episode_count = 0
    started_at = time.perf_counter()

    with _temporary_env(env_updates):
        get_settings.cache_clear()
        try:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass

            simulation_config = SimulationConfig(
                platform=PlatformType.TWITTER,
                agent_count=config.comparison_agent_count,
                memory_mode=mode,
                db_path=str(db_path),
                max_steps=max(1, config.comparison_steps),
                agent_source=AgentSource(source_type="template"),
            )
            init_result = await asyncio.wait_for(
                manager.initialize(simulation_config),
                timeout=max(1, config.comparison_timeout_seconds),
            )
            for _ in range(max(1, config.comparison_steps)):
                step_started = time.perf_counter()
                step_result = await asyncio.wait_for(
                    manager.step(),
                    timeout=max(1, config.comparison_timeout_seconds),
                )
                step_times_ms.append((time.perf_counter() - step_started) * 1000.0)
                step_snapshots.append(
                    {
                        "step_result": dict(step_result or {}),
                        "memory_debug": manager.get_memory_debug_info(),
                        "chat_history": _collect_manager_chat_history_stats(manager),
                    }
                )
            persisted_action_episode_count = _count_persisted_action_episodes(
                list(manager.get_all_agents())
            )
        except Exception as exc:
            return EvaluationEvent(
                phase="comparison",
                name=f"{mode.value}_short_comparison",
                status="blocked",
                metrics={"memory_mode": mode.value},
                reason=str(exc),
            )
        finally:
            try:
                await asyncio.wait_for(manager.close(), timeout=close_timeout)
            except TimeoutError:
                pass
            get_settings.cache_clear()
            shutil.rmtree(db_dir, ignore_errors=True)

    metrics = _summarize_comparison_run(
        mode=mode,
        init_result=init_result,
        manager_step_count=max(
            (int(snapshot.get("step_result", {}).get("step_executed", 0) or 0) for snapshot in step_snapshots),
            default=0,
        ),
        step_times_ms=step_times_ms,
        step_snapshots=step_snapshots,
        duration_ms=(time.perf_counter() - started_at) * 1000.0,
        persisted_action_episode_count=persisted_action_episode_count,
    )
    return EvaluationEvent(
        phase="comparison",
        name=f"{mode.value}_short_comparison",
        status="pass",
        metrics=metrics,
        evidence={"step_count": len(step_snapshots)},
    )


def _build_real_scenario_events(
    *,
    manager: OASISManager,
    init_result: dict[str, Any],
    config: EvaluationConfig,
    scenario_pack: dict[str, Any] | None = None,
    excluded_episode_keys: set[tuple[str, int | None, int | None]] | None = None,
) -> list[EvaluationEvent]:
    agents = list(manager.get_all_agents())
    store = getattr(manager, "_action_v1_longterm_store", None)
    raw_candidates = _collect_real_longterm_probe_candidates(store)
    excluded_episode_keys = excluded_episode_keys or set()
    candidates = [
        candidate
        for candidate in raw_candidates
        if _real_episode_key(candidate) not in excluded_episode_keys
    ]
    persisted_count = _count_persisted_action_episodes(agents)
    base_metrics = {
        "memory_mode": MemoryMode.ACTION_V1.value,
        "longterm_backend": (
            "openai_compatible" if config.embedding_url else "heuristic"
        ),
        "scenario_pack_id": str((scenario_pack or {}).get("id", "") or ""),
        "scenario_pack_purpose": str((scenario_pack or {}).get("purpose", "") or ""),
        "agent_count": int(init_result.get("agent_count", len(agents)) or len(agents)),
        "step_count": int(manager.get_state_info().get("current_step", 0) or 0),
        "actual_persisted_action_episode_count": persisted_count,
        "raw_real_probe_candidate_count": len(raw_candidates),
        "warmup_excluded_probe_candidate_count": len(raw_candidates) - len(candidates),
        **_summarize_real_probe_candidate_pool(
            candidates,
            probe_limit=max(0, config.scenario_probe_limit),
        ),
    }
    return [
        _build_real_self_action_retrievability_event(
            agents=agents,
            store=store,
            candidates=candidates,
            base_metrics=base_metrics,
        ),
        _build_real_continuity_recall_probe_event(
            agents=agents,
            store=store,
            candidates=candidates,
            base_metrics=base_metrics,
            next_step_id=int(manager.get_state_info().get("current_step", 0) or 0) + 1,
        ),
        _build_real_empty_observation_suppression_event(
            agents=agents,
            store=store,
            base_metrics=base_metrics,
            next_step_id=int(manager.get_state_info().get("current_step", 0) or 0) + 1,
        ),
    ]


def _build_real_longwindow_events(
    *,
    manager: OASISManager,
    init_result: dict[str, Any],
    config: EvaluationConfig,
    step_snapshots: list[dict[str, Any]],
) -> list[EvaluationEvent]:
    agents = list(manager.get_all_agents())
    persisted_count = _count_persisted_action_episodes(agents)
    longwindow_metrics = _summarize_longwindow_debug_snapshots(step_snapshots)
    base_metrics = {
        "memory_mode": MemoryMode.ACTION_V1.value,
        "longterm_backend": (
            "openai_compatible" if config.embedding_url else "heuristic"
        ),
        "agent_count": int(init_result.get("agent_count", len(agents)) or len(agents)),
        "step_count": int(manager.get_state_info().get("current_step", 0) or 0),
        "actual_persisted_action_episode_count": persisted_count,
        "persisted_action_episode_count": persisted_count,
        **longwindow_metrics,
    }
    status = (
        "pass"
        if persisted_count > 0
        and int(base_metrics.get("recall_injected_count", 0) or 0) > 0
        and int(base_metrics.get("recall_injected_trace_count", 0) or 0) > 0
        else "fail"
    )
    reason = ""
    if status != "pass":
        reason = (
            "Long-window run did not show recall injection in runtime snapshots "
            f"(persisted={persisted_count}, injected={base_metrics.get('recall_injected_count', 0)}, "
            f"trace_hits={base_metrics.get('recall_injected_trace_count', 0)})."
        )
    return [
        EvaluationEvent(
            phase="real-longwindow",
            name="VAL-RCL-10 real_longwindow_recall_injection",
            status=status,
            metrics=base_metrics,
            evidence={
                "trace_examples": _extract_longwindow_trace_examples(step_snapshots),
                "note": (
                    "该场景直接读取每步 memory debug snapshot 中的 recall 注入痕迹，"
                    "用于确认 recall 不只停留在 gate + retrieval。"
                ),
            },
            reason=reason,
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

    probe_candidates = _usable_real_probe_candidates(
        candidates,
        probe_limit=int(base_metrics.get("probe_attempt_limit", 5) or 0),
    )
    per_query: list[dict[str, Any]] = []
    for candidate in probe_candidates:
        query_text = _query_from_real_episode(candidate)
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


def _build_real_continuity_recall_probe_event(
    *,
    agents: list[Any],
    store: Any,
    candidates: list[dict[str, Any]],
    base_metrics: dict[str, Any],
    next_step_id: int,
) -> EvaluationEvent:
    if store is None:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-RCL-08 real_continuity_recall_probe",
            status="blocked",
            metrics=base_metrics,
            reason="No long-term store was available for continuity recall probe.",
        )
    if not candidates:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-RCL-08 real_continuity_recall_probe",
            status="blocked",
            metrics=base_metrics,
            reason="No real action episode candidate was available for continuity recall probe.",
        )

    target = candidates[0]
    agent = _context_agent_for_episode(agents, target) or _first_context_agent(agents)
    if agent is None:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-RCL-08 real_continuity_recall_probe",
            status="blocked",
            metrics=base_metrics,
            reason="No ContextSocialAgent was available for recall probe.",
        )

    snapshot = _related_snapshot_from_episode(target)
    query_text = _query_from_real_episode(target)
    perception = agent._observation_policy.build_perception_envelope(  # noqa: SLF001
        prompt_visible_snapshot=snapshot,
        observation_prompt=query_text,
    )
    preparation = agent._recall_planner.prepare(  # noqa: SLF001
        agent_id=target.get("agent_id"),
        topic=perception.topic,
        semantic_anchors=perception.semantic_anchors,
        entities=perception.entities,
        snapshot=perception.snapshot,
        memory_state=agent._memory_state,  # noqa: SLF001
        longterm_store=store,
        next_step_id=next_step_id,
        runtime_state=RecallRuntimeState(),
    )
    scored = _score_real_episode_retrieval_probe(
        expected=target,
        query_text=preparation.query_text,
        retrieved=preparation.candidates,
    )
    metrics = {
        **base_metrics,
        "probe_scope": "retrieve_only",
        "gate_decision": bool(preparation.gate_decision),
        "retrieval_attempted": bool(preparation.retrieval_attempted),
        "query_text": preparation.query_text,
        "recalled_count": preparation.recalled_count,
        "injected_count": 0,
        "retrieved_step_ids": preparation.recalled_step_ids,
        "first_hit_rank": scored["first_hit_rank"],
        "hit_at_3": scored["hit_at_3"],
    }
    return EvaluationEvent(
        phase="real-scenarios",
        name="VAL-RCL-08 real_continuity_recall_probe",
        status=(
            "pass"
            if preparation.gate_decision and scored["hit_at_3"]
            else "fail"
        ),
        metrics=metrics,
        evidence={
            "target_episode": _real_episode_debug_view(target),
            "gate_reason_flags": preparation.gate_reason_flags,
            "retrieved": [
                _real_episode_debug_view(item)
                for item in preparation.candidates[:3]
            ],
            "note": (
                "这是 retrieve-only probe：只走 gate + prepare + retrieval，"
                "不执行 prompt assemble，因此 injected_count 固定为 0。"
            ),
        },
    )


def _build_real_empty_observation_suppression_event(
    *,
    agents: list[Any],
    store: Any,
    base_metrics: dict[str, Any],
    next_step_id: int,
) -> EvaluationEvent:
    if store is None:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-RCL-09 real_empty_observation_recall_suppression",
            status="blocked",
            metrics=base_metrics,
            reason="No long-term store was available for suppression recall probe.",
        )

    agent = _first_context_agent(agents)
    if agent is None:
        return EvaluationEvent(
            phase="real-scenarios",
            name="VAL-RCL-09 real_empty_observation_recall_suppression",
            status="blocked",
            metrics=base_metrics,
            reason="No ContextSocialAgent was available for recall suppression probe.",
        )

    empty_snapshot = {
        "posts": {"success": True, "posts": []},
        "groups": {
            "success": True,
            "all_groups": [],
            "joined_group_ids": [],
            "messages": [],
            "degraded_groups": False,
            "degraded_messages": False,
            "message_count": 0,
        },
    }
    perception = agent._observation_policy.build_perception_envelope(  # noqa: SLF001
        prompt_visible_snapshot=empty_snapshot,
        observation_prompt="No new relevant social content is visible.",
    )
    preparation = agent._recall_planner.prepare(  # noqa: SLF001
        agent_id=getattr(agent, "agent_id", None),
        topic=perception.topic,
        semantic_anchors=perception.semantic_anchors,
        entities=perception.entities,
        snapshot=perception.snapshot,
        memory_state=agent._memory_state,  # noqa: SLF001
        longterm_store=store,
        next_step_id=next_step_id,
        runtime_state=RecallRuntimeState(),
    )
    metrics = {
        **base_metrics,
        "probe_scope": "retrieve_only",
        "gate_decision": bool(preparation.gate_decision),
        "retrieval_attempted": bool(preparation.retrieval_attempted),
        "recalled_count": preparation.recalled_count,
        "injected_count": 0,
    }
    return EvaluationEvent(
        phase="real-scenarios",
        name="VAL-RCL-09 real_empty_observation_recall_suppression",
        status=(
            "pass"
            if not preparation.gate_decision
            and not preparation.retrieval_attempted
            and preparation.recalled_count == 0
            else "fail"
        ),
        metrics=metrics,
        evidence={
            "gate_reason_flags": preparation.gate_reason_flags,
            "note": (
                "这是 retrieve-only probe：只验证空/无强信号 observation 下 gate / retrieval 是否被抑制；"
                "不执行 prompt assemble，因此 injected_count 固定为 0。"
            ),
        },
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


def _summarize_real_probe_candidate_pool(
    candidates: list[dict[str, Any]],
    *,
    probe_limit: int = 5,
) -> dict[str, Any]:
    considered = candidates[:probe_limit]
    usable = _usable_real_probe_candidates(candidates, probe_limit=probe_limit)
    missing_query_count = sum(
        1 for candidate in considered if not _query_from_real_episode(candidate)
    )
    outside_limit_count = max(0, len(candidates) - probe_limit)
    skipped_reason_counts: dict[str, int] = {}
    if missing_query_count:
        skipped_reason_counts["missing_query_text"] = missing_query_count
    if outside_limit_count:
        skipped_reason_counts["outside_probe_limit"] = outside_limit_count
    return {
        "real_probe_candidate_count": len(candidates),
        "probe_attempt_limit": probe_limit,
        "usable_probe_count": len(usable),
        "skipped_probe_count": missing_query_count + outside_limit_count,
        "skipped_probe_reason_counts": skipped_reason_counts,
        "candidate_action_name_distribution": _episode_field_distribution(
            candidates,
            "action_name",
        ),
        "candidate_agent_distribution": _episode_field_distribution(
            candidates,
            "agent_id",
        ),
        "usable_probe_action_name_distribution": _episode_field_distribution(
            usable,
            "action_name",
        ),
        "usable_probe_agent_distribution": _episode_field_distribution(
            usable,
            "agent_id",
        ),
    }


def _usable_real_probe_candidates(
    candidates: list[dict[str, Any]],
    *,
    probe_limit: int = 5,
) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in candidates[:probe_limit]
        if _query_from_real_episode(candidate)
    ]


def _episode_field_distribution(
    episodes: list[dict[str, Any]],
    field_name: str,
) -> dict[str, int]:
    return _count_string_values(
        [
            str(episode.get(field_name, "") or "unknown")
            for episode in episodes
        ]
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
        "expected_agent_id": expected_key[0],
        "expected_step_id": expected_key[1],
        "expected_action_index": expected_key[2],
        "expected_action_name": str(expected.get("action_name", "") or ""),
        "expected_episode": _real_episode_debug_view(expected),
        "retrieved_keys": retrieved_keys,
        "retrieved_labels": [_real_episode_label(item) for item in retrieved],
        "retrieved_action_names": [
            str(item.get("action_name", "") or "") for item in retrieved
        ],
        "retrieved_episodes": [_real_episode_debug_view(item) for item in retrieved],
        "retrieved_same_agent_flags": [
            key[0] == expected_key[0] for key in retrieved_keys
        ],
        "retrieved_same_step_flags": [
            key[1] == expected_key[1] for key in retrieved_keys
        ],
        "retrieved_top3_count": len(retrieved_keys[:3]),
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
        "top3_candidate_slot_count": sum(
            int(item.get("retrieved_top3_count", 0) or 0)
            for item in per_query
        ),
        "score_by_action_name": {
            row["action_name"]: {
                "query_count": row["query_count"],
                "hit_at_1": row["hit_at_1"],
                "hit_at_3": row["hit_at_3"],
                "mrr": row["mrr"],
                "miss_count": row["miss_count"],
            }
            for row in _probe_score_rows_by_action(per_query)
        },
    }


def _real_probe_readable_rows(per_query: list[dict[str, Any]]) -> list[str]:
    return [
        (
            f"{item['expected_label']}: top={item['retrieved_labels']} "
            f"expected={item['expected_key']} rank={item['first_hit_rank']}"
        )
        for item in per_query
    ]


def _probe_score_rows_by_action(per_query: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in per_query:
        action_name = str(item.get("expected_action_name", "") or "unknown")
        grouped.setdefault(action_name, []).append(item)
    rows: list[dict[str, Any]] = []
    for action_name, items in sorted(grouped.items()):
        count = len(items)
        rows.append(
            {
                "action_name": action_name,
                "query_count": count,
                "hit_at_1": _mean_bool(item.get("hit_at_1") for item in items),
                "hit_at_3": _mean_bool(item.get("hit_at_3") for item in items),
                "mrr": round(
                    sum(float(item.get("mrr", 0) or 0) for item in items)
                    / max(1, count),
                    4,
                ),
                "miss_count": sum(1 for item in items if not item.get("hit_at_3")),
            }
        )
    return rows


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
        f"idx={episode.get('action_index')} "
        f"action={episode.get('action_name')}"
    )


def _real_episode_debug_view(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": episode.get("agent_id"),
        "step_id": episode.get("step_id"),
        "action_index": episode.get("action_index"),
        "action_name": episode.get("action_name"),
        "action_fact": episode.get("action_fact"),
        "topic": episode.get("topic"),
        "query_source": episode.get("query_source"),
        "target_snapshot": episode.get("target_snapshot"),
    }


def _first_context_agent(agents: list[Any]) -> Any | None:
    for agent in agents:
        if hasattr(agent, "_recall_planner") and hasattr(agent, "_memory_state"):
            return agent
    return None


def _context_agent_for_episode(
    agents: list[Any],
    episode: dict[str, Any],
) -> Any | None:
    expected_agent_id = str(episode.get("agent_id", "") or "")
    if not expected_agent_id:
        return None
    for agent in agents:
        if (
            str(getattr(agent, "agent_id", "") or "") == expected_agent_id
            and hasattr(agent, "_recall_planner")
            and hasattr(agent, "_memory_state")
        ):
            return agent
    return None


def _related_snapshot_from_episode(episode: dict[str, Any]) -> dict[str, Any]:
    summary = _query_from_real_episode(episode) or "related remembered social content"
    target_snapshot = episode.get("target_snapshot", {}) or {}
    target_id = episode.get("target_id")
    if isinstance(target_snapshot, dict):
        target_id = target_snapshot.get("post_id", target_id)
    post_id = target_id if target_id is not None else 900001
    return {
        "posts": {
            "success": True,
            "posts": [
                {
                    "object_kind": "post",
                    "post_id": post_id,
                    "user_id": 900001,
                    "relation_anchor": "unknown",
                    "self_authored": False,
                    "summary": summary[:120],
                    "evidence_quality": "normal",
                    "degraded_evidence": False,
                    "comments_omitted_count": 0,
                    "comments": [],
                }
            ],
        },
        "groups": {
            "success": True,
            "all_groups": [],
            "joined_group_ids": [],
            "messages": [],
            "degraded_groups": False,
            "degraded_messages": False,
            "message_count": 0,
        },
    }


def _mean_bool(values: Any) -> float:
    collected = list(values)
    if not collected:
        return 0.0
    return round(sum(1.0 if item else 0.0 for item in collected) / len(collected), 4)


def _count_string_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _summarize_longwindow_debug_snapshots(
    step_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    agent_rows: list[dict[str, Any]] = []
    used_recall_step_ids: set[int] = set()
    observation_compression_trigger_count = 0
    for step_snapshot in step_snapshots:
        debug = step_snapshot.get("memory_debug", {}) or {}
        for agent in list(debug.get("agents", []) or []):
            agent_rows.append(agent)
            stage = str(agent.get("last_observation_stage", "") or "")
            if stage in {"long_text_capped", "interaction_reduced", "physical_fallback"}:
                observation_compression_trigger_count += 1
            for step_id in list(agent.get("last_injected_step_ids", []) or []):
                try:
                    used_recall_step_ids.add(int(step_id))
                except Exception:
                    continue

    prompt_tokens = [
        int(agent.get("last_prompt_tokens", 0) or 0)
        for agent in agent_rows
        if int(agent.get("last_prompt_tokens", 0) or 0) > 0
    ]
    return {
        "recall_gate_true_count": sum(
            1 for agent in agent_rows if bool(agent.get("last_recall_gate"))
        ),
        "recall_recalled_trace_count": sum(
            1 for agent in agent_rows if int(agent.get("last_recalled_count", 0) or 0) > 0
        ),
        "recall_recalled_not_injected_trace_count": sum(
            1
            for agent in agent_rows
            if int(agent.get("last_recalled_count", 0) or 0) > 0
            and int(agent.get("last_injected_count", 0) or 0) <= 0
        ),
        "recall_injected_count": sum(
            int(agent.get("last_injected_count", 0) or 0) for agent in agent_rows
        ),
        "recall_injected_trace_count": sum(
            1 for agent in agent_rows if int(agent.get("last_injected_count", 0) or 0) > 0
        ),
        "recall_overlap_filtered_count": sum(
            int(agent.get("last_recall_overlap_filtered_count", 0) or 0)
            for agent in agent_rows
        ),
        "recall_selection_stop_reason_counts": _count_string_values(
            [
                str(agent.get("last_recall_selection_stop_reason", "") or "")
                for agent in agent_rows
            ]
        ),
        "used_recall_step_ids": sorted(used_recall_step_ids),
        "avg_prompt_tokens": (
            round(sum(prompt_tokens) / len(prompt_tokens), 2) if prompt_tokens else 0.0
        ),
        "max_prompt_tokens": max(prompt_tokens, default=0),
        "observation_compression_trigger_count": observation_compression_trigger_count,
        "shortterm_recent_retained_step_count": max(
            (int(agent.get("recent_retained_step_count", 0) or 0) for agent in agent_rows),
            default=0,
        ),
        "shortterm_compressed_retained_step_count": max(
            (int(agent.get("compressed_retained_step_count", 0) or 0) for agent in agent_rows),
            default=0,
        ),
        "shortterm_total_retained_step_count": max(
            (int(agent.get("total_retained_step_count", 0) or 0) for agent in agent_rows),
            default=0,
        ),
    }


def _extract_longwindow_trace_examples(
    step_snapshots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step_snapshot in step_snapshots:
        step_result = dict(step_snapshot.get("step_result", {}) or {})
        step_id = int(step_result.get("step_executed", 0) or 0)
        debug = step_snapshot.get("memory_debug", {}) or {}
        for agent in list(debug.get("agents", []) or []):
            injected_count = int(agent.get("last_injected_count", 0) or 0)
            recalled_count = int(agent.get("last_recalled_count", 0) or 0)
            if injected_count <= 0 and recalled_count <= 0:
                continue
            rows.append(
                {
                    "step_id": step_id,
                    "agent_id": agent.get("agent_id"),
                    "user_name": agent.get("user_name"),
                    "last_recall_gate": agent.get("last_recall_gate"),
                    "last_recall_query_text": agent.get("last_recall_query_text"),
                    "last_recalled_count": recalled_count,
                    "last_injected_count": injected_count,
                    "last_recall_overlap_filtered_count": int(
                        agent.get("last_recall_overlap_filtered_count", 0) or 0
                    ),
                    "last_recall_selection_stop_reason": str(
                        agent.get("last_recall_selection_stop_reason", "") or ""
                    ),
                    "last_recalled_step_ids": list(agent.get("last_recalled_step_ids", []) or []),
                    "last_injected_step_ids": list(agent.get("last_injected_step_ids", []) or []),
                    "last_prompt_tokens": int(agent.get("last_prompt_tokens", 0) or 0),
                    "last_observation_stage": agent.get("last_observation_stage"),
                }
            )
    return rows[:5]


def _collect_manager_chat_history_stats(manager: OASISManager) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for agent in manager.get_all_agents():
        stats = _extract_agent_chat_history_stats(agent)
        if stats:
            rows.append(stats)
    return rows


def _extract_agent_chat_history_stats(agent: Any) -> dict[str, Any]:
    memory = getattr(agent, "memory", None)
    if memory is None:
        return {}

    stats: dict[str, Any] = {
        "memory_class": memory.__class__.__name__,
        "context_creator_class": "",
        "context_token_limit": 0,
        "window_size": None,
        "stored_record_count": 0,
        "retrieved_record_count": 0,
        "selected_context_message_count": 0,
        "stored_raw_tokens": 0,
        "selected_context_tokens": 0,
        "window_dropped_record_count": 0,
        "token_selection_dropped_record_count": 0,
        "stored_observation_round_count": 0,
        "selected_observation_round_count": 0,
        "dropped_observation_round_count": 0,
        "window_drop_active": False,
        "token_truncation_active": False,
    }

    context_creator = None
    try:
        context_creator = memory.get_context_creator()
    except Exception:
        context_creator = None
    if context_creator is not None:
        stats["context_creator_class"] = context_creator.__class__.__name__
        token_limit = getattr(context_creator, "token_limit", None)
        if isinstance(token_limit, int):
            stats["context_token_limit"] = token_limit

    window_size = getattr(memory, "window_size", getattr(memory, "_window_size", None))
    if isinstance(window_size, int):
        stats["window_size"] = window_size

    raw_memory_records: list[MemoryRecord] = []
    storage = getattr(getattr(memory, "_chat_history_block", None), "storage", None)
    load = getattr(storage, "load", None)
    if callable(load):
        try:
            raw_records = load()
        except Exception:
            raw_records = []
        if isinstance(raw_records, list):
            stats["stored_record_count"] = len(raw_records)
            try:
                raw_memory_records = [
                    MemoryRecord.from_dict(record)
                    for record in raw_records
                    if isinstance(record, dict)
                ]
            except Exception:
                raw_memory_records = []

    token_counter = getattr(context_creator, "token_counter", None)
    if token_counter is not None and raw_memory_records:
        try:
            raw_messages = [record.to_openai_message() for record in raw_memory_records]
            stats["stored_raw_tokens"] = int(
                token_counter.count_tokens_from_messages(raw_messages)
            )
        except Exception:
            stats["stored_raw_tokens"] = 0
    if raw_memory_records:
        stats["stored_observation_round_count"] = sum(
            1
            for record in raw_memory_records
            if _is_observation_prompt_text(
                (record.to_openai_message() or {}).get("content", "")
            )
        )

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            retrieved_records = memory.retrieve()
        except Exception:
            retrieved_records = []
        try:
            selected_messages, selected_tokens = memory.get_context()
        except Exception:
            selected_messages, selected_tokens = [], 0

    if isinstance(retrieved_records, list):
        stats["retrieved_record_count"] = len(retrieved_records)
    if isinstance(selected_messages, list):
        stats["selected_context_message_count"] = len(selected_messages)
    if isinstance(selected_tokens, int):
        stats["selected_context_tokens"] = selected_tokens

    selected_record_indices = _match_selected_record_indices(
        retrieved_records=(
            retrieved_records if isinstance(retrieved_records, list) else []
        ),
        selected_messages=selected_messages if isinstance(selected_messages, list) else [],
    )
    if selected_record_indices and isinstance(retrieved_records, list):
        selected_records = [
            retrieved_records[index]
            for index in selected_record_indices
            if 0 <= index < len(retrieved_records)
        ]
        stats["selected_observation_round_count"] = sum(
            1
            for record in selected_records
            if getattr(record, "memory_record", None) is not None
            and _is_observation_prompt_text(
                (record.memory_record.to_openai_message() or {}).get("content", "")
            )
        )

    stats["dropped_observation_round_count"] = max(
        0,
        int(stats["stored_observation_round_count"])
        - int(stats["selected_observation_round_count"]),
    )
    stats["window_dropped_record_count"] = max(
        0,
        int(stats["stored_record_count"]) - int(stats["retrieved_record_count"]),
    )
    stats["token_selection_dropped_record_count"] = max(
        0,
        int(stats["retrieved_record_count"])
        - int(stats["selected_context_message_count"]),
    )
    stats["window_drop_active"] = stats["window_dropped_record_count"] > 0

    token_limit = int(stats["context_token_limit"] or 0)
    raw_tokens = int(stats["stored_raw_tokens"] or 0)
    stats["token_truncation_active"] = bool(
        token_limit > 0
        and (
            raw_tokens > token_limit
            or stats["token_selection_dropped_record_count"] > 0
        )
    )
    return stats


def _message_match_key(message: Any) -> str:
    try:
        return json.dumps(message, sort_keys=True, ensure_ascii=False, default=str)
    except TypeError:
        return str(message)


def _is_observation_prompt_text(content: Any) -> bool:
    text = str(content or "")
    return "After refreshing" in text and "pick one you want to perform action" in text


def _match_selected_record_indices(
    *,
    retrieved_records: list[Any],
    selected_messages: list[dict[str, Any]],
) -> list[int]:
    retrieved_keys = [
        _message_match_key(record.memory_record.to_openai_message())
        for record in retrieved_records
        if getattr(record, "memory_record", None) is not None
    ]
    selected_keys = [_message_match_key(message) for message in selected_messages]

    matched_indices: list[int] = []
    search_from = 0
    for selected_key in selected_keys:
        try:
            index = retrieved_keys.index(selected_key, search_from)
        except ValueError:
            continue
        matched_indices.append(index)
        search_from = index + 1
    return matched_indices


def _summarize_comparison_run(
    *,
    mode: MemoryMode,
    init_result: dict[str, Any],
    manager_step_count: int,
    step_times_ms: list[float],
    step_snapshots: list[dict[str, Any]],
    duration_ms: float,
    persisted_action_episode_count: int,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "memory_mode": mode.value,
        "agent_count": int(init_result.get("agent_count", 0) or 0),
        "step_count": manager_step_count,
        "step_success_rate": 1.0 if step_snapshots else 0.0,
        "avg_step_time_ms": (
            round(sum(step_times_ms) / len(step_times_ms), 3) if step_times_ms else 0.0
        ),
        "max_step_time_ms": round(max(step_times_ms), 3) if step_times_ms else 0.0,
        "duration_ms": round(duration_ms, 3),
    }

    if mode == MemoryMode.ACTION_V1:
        debug_snapshots = [
            {"memory_debug": snapshot.get("memory_debug", {}) or {}}
            for snapshot in step_snapshots
        ]
        longwindow_like = _summarize_longwindow_debug_snapshots(debug_snapshots)
        metrics.update(
            {
                "avg_prompt_tokens": longwindow_like["avg_prompt_tokens"],
                "max_prompt_tokens": longwindow_like["max_prompt_tokens"],
                "persisted_action_episode_count": int(persisted_action_episode_count or 0),
                "recall_gate_true_count": longwindow_like["recall_gate_true_count"],
                "recall_recalled_trace_count": longwindow_like["recall_recalled_trace_count"],
                "recall_recalled_not_injected_trace_count": longwindow_like[
                    "recall_recalled_not_injected_trace_count"
                ],
                "recall_injected_count": longwindow_like["recall_injected_count"],
                "recall_injected_trace_count": longwindow_like["recall_injected_trace_count"],
                "recall_overlap_filtered_count": longwindow_like["recall_overlap_filtered_count"],
                "recall_selection_stop_reason_counts": longwindow_like[
                    "recall_selection_stop_reason_counts"
                ],
                "shortterm_recent_retained_step_count": longwindow_like[
                    "shortterm_recent_retained_step_count"
                ],
                "shortterm_compressed_retained_step_count": longwindow_like[
                    "shortterm_compressed_retained_step_count"
                ],
                "shortterm_total_retained_step_count": longwindow_like[
                    "shortterm_total_retained_step_count"
                ],
                "observation_compression_trigger_count": longwindow_like[
                    "observation_compression_trigger_count"
                ],
            }
        )
        return metrics

    chat_history_entries: list[dict[str, Any]] = [
        agent_stats
        for snapshot in step_snapshots
        for agent_stats in list(snapshot.get("chat_history", []) or [])
        if isinstance(agent_stats, dict)
    ]

    def _max_chat_history_metric(key: str) -> int:
        values = [int(item.get(key, 0) or 0) for item in chat_history_entries]
        return max(values) if values else 0

    metrics.update(
        {
            "chat_history_token_truncation_active_count": sum(
                1 for item in chat_history_entries if item.get("token_truncation_active")
            ),
            "chat_history_window_drop_active_count": sum(
                1 for item in chat_history_entries if item.get("window_drop_active")
            ),
            "chat_history_context_token_limit": _max_chat_history_metric(
                "context_token_limit"
            ),
            "max_chat_history_stored_raw_tokens": _max_chat_history_metric(
                "stored_raw_tokens"
            ),
            "max_chat_history_selected_context_tokens": _max_chat_history_metric(
                "selected_context_tokens"
            ),
            "max_chat_history_stored_record_count": _max_chat_history_metric(
                "stored_record_count"
            ),
            "max_chat_history_selected_context_message_count": _max_chat_history_metric(
                "selected_context_message_count"
            ),
            "max_chat_history_token_selection_dropped_record_count": _max_chat_history_metric(
                "token_selection_dropped_record_count"
            ),
            "max_chat_history_window_dropped_record_count": _max_chat_history_metric(
                "window_dropped_record_count"
            ),
            "peak_chat_history_stored_observation_round_count": _max_chat_history_metric(
                "stored_observation_round_count"
            ),
            "peak_chat_history_selected_observation_round_count": _max_chat_history_metric(
                "selected_observation_round_count"
            ),
        }
    )
    return metrics


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
