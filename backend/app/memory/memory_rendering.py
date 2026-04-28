from __future__ import annotations

from dataclasses import dataclass, field

from .config import SummaryPresetConfig
from .episodic_memory import HeartbeatRange, StepSegment
from .working_memory import ActionSummaryBlock


@dataclass(slots=True)
class RecentTurnView:
    step_id: int
    user_view: str
    assistant_view: str
    action_keys: list[tuple[int, int]] = field(default_factory=list)


@dataclass(slots=True)
class CompressedNoteView:
    kind: str
    sort_key: int
    text: str
    source_action_keys: list[tuple[int, int]] = field(default_factory=list)
    covered_step_ids: list[int] = field(default_factory=list)


def build_recent_turn_view(
    segment: StepSegment,
    *,
    summary_preset: SummaryPresetConfig,
) -> RecentTurnView:
    perception = segment.perception_records[0] if segment.perception_records else None
    observation_prompt = ""
    if perception is not None:
        observation_prompt = str(perception.metadata.get("observation_prompt", "") or "").strip()
        if not observation_prompt:
            observation_prompt = perception.content.strip()

    user_view = "<historical_observation>\n" + observation_prompt
    action_lines: list[str] = []
    action_keys: list[tuple[int, int]] = []
    aggregated_state_changes: list[str] = []
    for index, decision in enumerate(
        segment.decision_records[: summary_preset.max_action_items_per_recent_turn]
    ):
        evidence = decision.metadata.get("action_evidence", {}) or {}
        target_summary = _clip(
            _target_summary_from_evidence(evidence),
            summary_preset.max_target_summary_chars,
        )
        execution_status = str(evidence.get("execution_status", "") or "unknown")
        action_fact = str(decision.metadata.get("action", decision.content) or "").strip()
        line = f"- [{index}] {action_fact}"
        if target_summary or not summary_preset.omit_empty_template_fields:
            line += f" target={target_summary}"
        line += f" status={execution_status}"
        action_lines.append(line)
        action_keys.append((segment.step_id, index))
        if index < len(segment.action_result_records):
            state_changes = (
                segment.action_result_records[index].metadata.get("state_changes", []) or []
            )
            for item in state_changes:
                if item and item not in aggregated_state_changes:
                    aggregated_state_changes.append(str(item))

    if not action_lines:
        action_lines.append("- none")

    assistant_lines = ["Actions:", *action_lines]
    if aggregated_state_changes:
        assistant_lines.append(
            "State changes: "
            + ", ".join(aggregated_state_changes[: summary_preset.max_state_changes_per_turn])
        )
    elif not summary_preset.omit_empty_template_fields:
        assistant_lines.append("State changes: none")
    outcome = _segment_outcome_digest(segment)
    if outcome:
        assistant_lines.append(
            "Outcome: " + _clip(outcome, summary_preset.max_outcome_digest_chars)
        )
    elif not summary_preset.omit_empty_template_fields:
        assistant_lines.append("Outcome: none")
    return RecentTurnView(
        step_id=segment.step_id,
        user_view=user_view,
        assistant_view="\n".join(assistant_lines),
        action_keys=action_keys,
    )


def build_action_block_note_view(
    block: ActionSummaryBlock,
    *,
    summary_preset: SummaryPresetConfig,
) -> CompressedNoteView:
    body_lines = [
        summary_preset.compressed_note_title,
        f"Steps {block.step_start}-{block.step_end} on {block.platform}.",
    ]
    if block.action_items:
        body_lines.append("Actions:")
        for action in block.action_items[: summary_preset.max_action_items_per_block]:
            line = f"- [{action.step_id}:{action.action_index}] {action.action_fact}"
            if action.target_summary or not summary_preset.omit_empty_template_fields:
                line += f" target={action.target_summary}"
            line += f" status={action.execution_status}"
            body_lines.append(line)
    elif not summary_preset.omit_empty_template_fields:
        body_lines.extend(["Actions:", "- none"])
    if block.semantic_anchors:
        anchors = [
            _clip(str(anchor), summary_preset.max_local_context_chars)
            for anchor in block.semantic_anchors[: summary_preset.max_anchor_items_per_block]
        ]
        body_lines.append("Anchors: " + " | ".join(anchors))
    elif not summary_preset.omit_empty_template_fields:
        body_lines.append("Anchors: none")
    if block.first_outcome_digest or block.last_outcome_digest:
        first = _clip(block.first_outcome_digest, summary_preset.max_outcome_digest_chars)
        last = _clip(block.last_outcome_digest, summary_preset.max_outcome_digest_chars)
        body_lines.append(f"Outcome window: first={first} ; last={last}")
    elif not summary_preset.omit_empty_template_fields:
        body_lines.append("Outcome window: none")
    return CompressedNoteView(
        kind="action_block",
        sort_key=block.step_end,
        text="\n".join(body_lines),
        source_action_keys=list(block.source_action_keys),
        covered_step_ids=list(block.covered_step_ids),
    )


def build_heartbeat_note_view(
    heartbeat: HeartbeatRange,
    *,
    summary_preset: SummaryPresetConfig,
) -> CompressedNoteView:
    lines = [summary_preset.compressed_note_title, heartbeat.to_summary_text()]
    return CompressedNoteView(
        kind="heartbeat",
        sort_key=heartbeat.end_step,
        text="\n".join(lines),
        covered_step_ids=list(range(heartbeat.start_step, heartbeat.end_step + 1)),
    )


def _target_summary_from_evidence(evidence: dict[str, object]) -> str:
    target_snapshot = evidence.get("target_snapshot", {}) or {}
    if isinstance(target_snapshot, dict):
        summary = str(target_snapshot.get("summary", "") or "").strip()
        if summary:
            return summary
    target_type = str(evidence.get("target_type", "") or "").strip()
    target_id = evidence.get("target_id")
    if target_type and target_id is not None:
        return f"{target_type}:{target_id}"
    return target_type


def _segment_outcome_digest(segment: StepSegment) -> str:
    for record in reversed(segment.final_outcome_records):
        text = record.content.strip()
        if text:
            return text
    for record in reversed(segment.action_result_records):
        text = record.content.strip()
        if text:
            return text
    for record in reversed(segment.decision_records):
        text = record.content.strip()
        if text:
            return text
    return ""


def _clip(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"
