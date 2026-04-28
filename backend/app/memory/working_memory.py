from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .action_significance import (
    infer_action_significance,
    is_memory_worthy_action,
    normalize_execution_status,
)
from .config import SummaryPresetConfig
from .episodic_memory import ActionEpisode, EpisodeRecord, HeartbeatRange, StepRecord, StepSegment


@dataclass(slots=True)
class ActionItem:
    step_id: int
    action_index: int
    action_name: str
    action_fact: str
    target_type: str = ""
    target_id: Any = None
    target_summary: str = ""
    local_context_digest: str = ""
    authored_content_excerpt: str = ""
    state_changes: list[str] = field(default_factory=list)
    execution_status: str = "unknown"
    target_resolution_status: str = ""
    target_evidence_quality: str = ""
    degraded_evidence: bool = False
    action_significance: str = ""


@dataclass(slots=True)
class ActionSummaryBlock:
    memory_kind: str
    agent_id: str
    step_start: int
    step_end: int
    start_timestamp: float
    end_timestamp: float
    platform: str
    action_items: list[ActionItem] = field(default_factory=list)
    topic: str = ""
    semantic_anchors: list[str] = field(default_factory=list)
    action_count: int = 0
    first_outcome_digest: str = ""
    last_outcome_digest: str = ""
    outcome_digest: str = ""
    source_action_keys: list[tuple[int, int]] = field(default_factory=list)
    summary_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def covered_step_ids(self) -> list[int]:
        return list(range(self.step_start, self.step_end + 1))


@dataclass(slots=True)
class RecentWorkingMemory:
    segments: list[StepSegment] = field(default_factory=list)
    step_action_episodes: dict[int, list[ActionEpisode]] = field(default_factory=dict)


@dataclass(slots=True)
class CompressedWorkingMemory:
    action_blocks: list[ActionSummaryBlock] = field(default_factory=list)
    heartbeat_ranges: list[HeartbeatRange] = field(default_factory=list)


@dataclass(slots=True)
class MemoryState:
    recent: RecentWorkingMemory = field(default_factory=RecentWorkingMemory)
    compressed: CompressedWorkingMemory = field(default_factory=CompressedWorkingMemory)


@dataclass(slots=True)
class RecallOverlapState:
    exact_action_keys: set[tuple[int, int]] = field(default_factory=set)
    non_action_step_ids: set[int] = field(default_factory=set)
    conservative_action_step_ids: set[int] = field(default_factory=set)
    recent_action_keys: set[tuple[int, int]] = field(default_factory=set)
    recent_step_ids: set[int] = field(default_factory=set)
    compressed_action_keys: set[tuple[int, int]] = field(default_factory=set)
    compressed_conservative_step_ids: set[int] = field(default_factory=set)


@dataclass(slots=True)
class RecallOverlapFilterDecision:
    step_id: int | None
    action_index: int | None
    filtered: bool
    reason: str


def episode_record_to_action_summary_block(episode: EpisodeRecord) -> ActionSummaryBlock:
    action_items = [
        ActionItem(
            step_id=episode.step_id,
            action_index=index,
            action_name=str(action),
            action_fact=str(action),
        )
        for index, action in enumerate(episode.actions)
    ]
    summary_lines = [
        f"Compressed memory for steps {episode.step_id}-{episode.step_id} on {episode.platform}.",
    ]
    if action_items:
        summary_lines.append("Actions: " + ", ".join(item.action_fact for item in action_items))
    if episode.semantic_anchors:
        summary_lines.append("Anchors: " + " | ".join(str(anchor) for anchor in episode.semantic_anchors))
    if episode.outcome:
        summary_lines.append(f"Outcome: {episode.outcome}")
    return ActionSummaryBlock(
        memory_kind="action_summary_block",
        agent_id=episode.agent_id,
        step_start=episode.step_id,
        step_end=episode.step_id,
        start_timestamp=episode.timestamp,
        end_timestamp=episode.timestamp,
        platform=episode.platform,
        action_items=action_items,
        topic=episode.topic,
        semantic_anchors=list(episode.semantic_anchors),
        action_count=len(action_items),
        first_outcome_digest=episode.outcome,
        last_outcome_digest=episode.outcome,
        outcome_digest=episode.outcome,
        source_action_keys=[],
        summary_text="\n".join(summary_lines),
        metadata={
            "legacy_episode_record": True,
            "legacy_action_count": len(episode.actions),
            "legacy_state_changes": list(episode.state_changes),
        },
    )


def build_action_summary_block(
    *,
    segment: StepSegment,
    action_episodes: list[ActionEpisode],
    summary_preset: SummaryPresetConfig,
) -> ActionSummaryBlock | None:
    action_items = [
        build_action_item(episode=episode, summary_preset=summary_preset)
        for episode in action_episodes
        if is_memory_worthy_action_episode(episode)
    ]
    if not action_items:
        return None

    source_action_keys = [(item.step_id, item.action_index) for item in action_items]
    semantic_anchors = _segment_semantic_anchors(segment, summary_preset=summary_preset)
    outcome = _segment_outcome(segment)
    block = ActionSummaryBlock(
        memory_kind="action_summary_block",
        agent_id=segment.agent_id,
        step_start=segment.step_id,
        step_end=segment.step_id,
        start_timestamp=segment.timestamp,
        end_timestamp=segment.timestamp,
        platform=segment.platform,
        action_items=action_items,
        topic=_segment_topic(segment),
        semantic_anchors=semantic_anchors,
        action_count=len(action_items),
        first_outcome_digest=outcome,
        last_outcome_digest=outcome,
        outcome_digest=outcome,
        source_action_keys=source_action_keys,
        metadata={
            "total_decision_count": len(segment.decision_records),
            "omitted_action_count": max(0, len(segment.decision_records) - len(action_items)),
        },
    )
    block.summary_text = render_action_summary_block_text(block, summary_preset=summary_preset)
    return block


def build_action_item(
    *,
    episode: ActionEpisode,
    summary_preset: SummaryPresetConfig,
) -> ActionItem:
    target_snapshot = dict(episode.target_snapshot or {})
    target_evidence_quality = str(
        target_snapshot.get("evidence_quality", "") or episode.evidence_quality or ""
    ).strip()
    if not target_evidence_quality:
        target_evidence_quality = "normal" if target_snapshot else "missing"
    return ActionItem(
        step_id=episode.step_id,
        action_index=episode.action_index,
        action_name=episode.action_name,
        action_fact=episode.action_fact or episode.action_name,
        target_type=episode.target_type,
        target_id=episode.target_id,
        target_summary=_clip(_episode_target_summary(episode), summary_preset.max_target_summary_chars),
        local_context_digest=_clip(
            _episode_local_context_digest(episode), summary_preset.max_local_context_chars
        ),
        authored_content_excerpt=_clip(
            str(episode.authored_content or "").strip(),
            summary_preset.max_authored_excerpt_chars,
        ),
        state_changes=list(episode.state_changes),
        execution_status=normalize_execution_status(episode.execution_status),
        target_resolution_status=str(episode.target_resolution_status or "").strip(),
        target_evidence_quality=target_evidence_quality,
        degraded_evidence=bool(
            episode.degraded_evidence or target_snapshot.get("degraded_evidence", False)
        ),
        action_significance=str(
            episode.action_significance
            or infer_action_significance(
                action_name=episode.action_name,
                authored_content=episode.authored_content,
            )
        ).strip(),
    )


def render_action_summary_block_text(
    block: ActionSummaryBlock,
    *,
    summary_preset: SummaryPresetConfig,
) -> str:
    lines = [f"Compressed memory for steps {block.step_start}-{block.step_end} on {block.platform}."]
    if block.action_items:
        lines.append("Actions:")
        for item in block.action_items[: summary_preset.max_action_items_per_block]:
            line = f"- [{item.step_id}:{item.action_index}] {item.action_fact}"
            if item.target_summary:
                line += f" target={item.target_summary}"
            line += f" status={item.execution_status}"
            lines.append(line)
    if block.semantic_anchors:
        anchors = " | ".join(
            _clip(str(anchor), summary_preset.max_local_context_chars)
            for anchor in block.semantic_anchors[: summary_preset.max_anchor_items_per_block]
        )
        lines.append(f"Anchors: {anchors}")
    if block.first_outcome_digest or block.last_outcome_digest:
        first = _clip(block.first_outcome_digest, summary_preset.max_outcome_digest_chars)
        last = _clip(block.last_outcome_digest, summary_preset.max_outcome_digest_chars)
        lines.append(f"Outcome window: first={first} ; last={last}")
    return "\n".join(lines)


def is_memory_worthy_action_episode(episode: ActionEpisode) -> bool:
    action_significance = str(
        episode.action_significance
        or infer_action_significance(
            action_name=episode.action_name,
            authored_content=episode.authored_content,
        )
    ).strip()
    return is_memory_worthy_action(
        execution_status=episode.execution_status,
        action_significance=action_significance,
    )


def recent_action_seed_payloads(segments: Iterable[StepSegment]) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for segment in segments:
        outcome = _segment_outcome(segment)
        for index, decision in enumerate(segment.decision_records):
            evidence = decision.metadata.get("action_evidence", {}) or {}
            action_name = str(decision.metadata.get("action_name", "") or "").strip()
            action_fact = str(decision.metadata.get("action", decision.content) or "").strip()
            target_snapshot = dict(evidence.get("target_snapshot", {}) or {})
            target_type = str(evidence.get("target_type", "") or "").strip()
            target_id = evidence.get("target_id")
            if not action_name and not action_fact and not target_snapshot and not target_type:
                continue
            local_context = dict(evidence.get("local_context", {}) or {})
            payloads.append(
                {
                    "memory_kind": "recent_action_seed",
                    "step_id": segment.step_id,
                    "action_index": index,
                    "platform": segment.platform,
                    "action_name": action_name,
                    "action_fact": action_fact or action_name,
                    "target_type": target_type,
                    "target_id": target_id,
                    "target_snapshot": target_snapshot,
                    "local_context": local_context,
                    "authored_content": str(evidence.get("authored_content", "") or ""),
                    "state_changes": list(_matching_state_changes(segment.action_result_records, index)),
                    "outcome": outcome,
                }
            )
    return payloads


def recent_action_target_refs(segments: Iterable[StepSegment]) -> list[str]:
    refs: list[str] = []
    for payload in recent_action_seed_payloads(segments):
        target_type = str(payload.get("target_type", "") or "").strip()
        target_id = payload.get("target_id")
        if target_type and target_id is not None:
            refs.append(f"{target_type}:{target_id}")
    return list(dict.fromkeys(refs))


def build_recall_overlap_state_from_memory_state(memory_state: MemoryState) -> RecallOverlapState:
    recent_action_keys = {
        (segment.step_id, index)
        for segment in memory_state.recent.segments
        for index, _ in enumerate(segment.decision_records)
    }
    recent_step_ids = {segment.step_id for segment in memory_state.recent.segments}
    compressed_conservative_step_ids = {
        step_id
        for block in memory_state.compressed.action_blocks
        if not block.source_action_keys
        for step_id in block.covered_step_ids
    }
    compressed_action_keys = {
        action_key
        for block in memory_state.compressed.action_blocks
        for action_key in block.source_action_keys
    }
    compressed_conservative_step_ids.update(
        step_id
        for heartbeat in memory_state.compressed.heartbeat_ranges
        for step_id in range(heartbeat.start_step, heartbeat.end_step + 1)
    )
    return RecallOverlapState(
        exact_action_keys=recent_action_keys | compressed_action_keys,
        non_action_step_ids=recent_step_ids,
        conservative_action_step_ids=compressed_conservative_step_ids,
        recent_action_keys=recent_action_keys,
        recent_step_ids=recent_step_ids,
        compressed_action_keys=compressed_action_keys,
        compressed_conservative_step_ids=compressed_conservative_step_ids,
    )


def build_recall_overlap_state_from_views(
    *,
    recent_turns: Iterable[Any],
    compressed_notes: Iterable[Any],
) -> RecallOverlapState:
    recent_action_keys: set[tuple[int, int]] = set()
    recent_step_ids: set[int] = set()
    compressed_action_keys: set[tuple[int, int]] = set()
    compressed_conservative_step_ids: set[int] = set()

    for view in recent_turns:
        step_id = _parse_step_id(getattr(view, "step_id", None))
        if step_id is not None:
            recent_step_ids.add(step_id)
        recent_action_keys.update(
            action_key
            for action_key in getattr(view, "action_keys", []) or []
            if _is_action_key(action_key)
        )

    for note in compressed_notes:
        source_action_keys = list(getattr(note, "source_action_keys", []) or [])
        compressed_action_keys.update(
            action_key for action_key in source_action_keys if _is_action_key(action_key)
        )
        covered_step_ids = {
            step_id
            for step_id in getattr(note, "covered_step_ids", []) or []
            if isinstance(step_id, int)
        }
        note_kind = str(getattr(note, "kind", "") or "").strip()
        if note_kind == "heartbeat" or not source_action_keys:
            compressed_conservative_step_ids.update(covered_step_ids)

    return RecallOverlapState(
        exact_action_keys=recent_action_keys | compressed_action_keys,
        non_action_step_ids=recent_step_ids,
        conservative_action_step_ids=compressed_conservative_step_ids,
        recent_action_keys=recent_action_keys,
        recent_step_ids=recent_step_ids,
        compressed_action_keys=compressed_action_keys,
        compressed_conservative_step_ids=compressed_conservative_step_ids,
    )


def explain_recall_candidates_by_overlap(
    recall_candidates: Iterable[Mapping[str, Any]],
    overlap_state: RecallOverlapState,
) -> list[RecallOverlapFilterDecision]:
    decisions: list[RecallOverlapFilterDecision] = []
    non_action_step_ids = overlap_state.non_action_step_ids | overlap_state.conservative_action_step_ids
    for candidate in recall_candidates:
        step_id = _parse_step_id(candidate.get("step_id"))
        action_index = candidate.get("action_index")
        parsed_action_index = action_index if isinstance(action_index, int) else None
        if step_id is None:
            decisions.append(
                RecallOverlapFilterDecision(
                    step_id=None,
                    action_index=parsed_action_index,
                    filtered=False,
                    reason="missing_step_id",
                )
            )
            continue

        reason = "kept"
        filtered = False
        if _is_action_episode_payload(candidate):
            action_key = (step_id, parsed_action_index) if parsed_action_index is not None else None
            if action_key is not None and action_key in overlap_state.exact_action_keys:
                filtered = True
                if action_key in overlap_state.recent_action_keys:
                    reason = "recent_exact_action_overlap"
                elif action_key in overlap_state.compressed_action_keys:
                    reason = "compressed_exact_action_overlap"
                else:
                    reason = "exact_action_overlap"
            elif step_id in overlap_state.conservative_action_step_ids:
                filtered = True
                if step_id in overlap_state.compressed_conservative_step_ids:
                    reason = "compressed_conservative_step_overlap"
                else:
                    reason = "conservative_step_overlap"
        elif step_id in non_action_step_ids:
            filtered = True
            if step_id in overlap_state.recent_step_ids:
                reason = "recent_step_overlap"
            elif step_id in overlap_state.compressed_conservative_step_ids:
                reason = "compressed_conservative_step_overlap"
            else:
                reason = "step_overlap"

        decisions.append(
            RecallOverlapFilterDecision(
                step_id=step_id,
                action_index=parsed_action_index,
                filtered=filtered,
                reason=reason,
            )
        )
    return decisions


def filter_recall_candidates_by_overlap(
    recall_candidates: Iterable[Mapping[str, Any]],
    overlap_state: RecallOverlapState,
) -> list[Mapping[str, Any]]:
    filtered: list[Mapping[str, Any]] = []
    non_action_step_ids = overlap_state.non_action_step_ids | overlap_state.conservative_action_step_ids
    for candidate in recall_candidates:
        step_id = _parse_step_id(candidate.get("step_id"))
        if step_id is None:
            filtered.append(candidate)
            continue
        if _is_action_episode_payload(candidate):
            action_index = candidate.get("action_index")
            if isinstance(action_index, int) and (step_id, action_index) in overlap_state.exact_action_keys:
                continue
            if step_id in overlap_state.conservative_action_step_ids:
                continue
        elif step_id in non_action_step_ids:
            continue
        filtered.append(candidate)
    return filtered


def _matching_state_changes(action_result_records: list[StepRecord], action_index: int) -> list[str]:
    if action_index >= len(action_result_records):
        return []
    return list(action_result_records[action_index].metadata.get("state_changes", []) or [])


def _segment_outcome(segment: StepSegment) -> str:
    for record in reversed(segment.final_outcome_records):
        text = record.content.strip()
        if text:
            return text
    for record in reversed(segment.action_result_records):
        text = record.content.strip()
        if text:
            return text
    return ""


def _segment_semantic_anchors(
    segment: StepSegment,
    *,
    summary_preset: SummaryPresetConfig,
) -> list[str]:
    anchors: list[str] = []
    for record in segment.perception_records:
        anchors.extend(record.metadata.get("semantic_anchors", []))
    deduped = list(dict.fromkeys(str(item).strip() for item in anchors if str(item).strip()))
    return deduped[: summary_preset.max_anchor_items_per_block]


def _segment_topic(segment: StepSegment) -> str:
    for record in segment.perception_records:
        topic = str(record.metadata.get("topic", "") or "").strip()
        if topic:
            return topic
    return ""


def _episode_target_summary(episode: ActionEpisode) -> str:
    summary = str((episode.target_snapshot or {}).get("summary", "") or "").strip()
    if summary:
        return summary
    if episode.target_type and episode.target_id is not None:
        return f"{episode.target_type}:{episode.target_id}"
    return str(episode.target_type or "").strip()


def _episode_local_context_digest(episode: ActionEpisode) -> str:
    context = episode.local_context or {}
    parent_post = context.get("parent_post") or {}
    if isinstance(parent_post, dict):
        summary = str(parent_post.get("summary", "") or "").strip()
        if summary:
            return f"parent post {summary}"
    group = context.get("group") or {}
    if isinstance(group, dict):
        summary = str(group.get("summary", "") or "").strip()
        if summary:
            return f"group {summary}"
    visible_comments = context.get("visible_comments") or []
    if visible_comments:
        first = visible_comments[0]
        if isinstance(first, dict):
            summary = str(first.get("summary", "") or "").strip()
            if summary:
                return f"visible comment {summary}"
    visible_messages = context.get("visible_messages") or []
    if visible_messages:
        first = visible_messages[0]
        if isinstance(first, dict):
            summary = str(first.get("summary", "") or "").strip()
            if summary:
                return f"visible message {summary}"
    return ""


def _is_action_episode_payload(item: Mapping[str, Any]) -> bool:
    return str(item.get("memory_kind", "") or "") == "action_episode"


def _parse_step_id(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_action_key(value: Any) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
    )


def _clip(text: str, limit: int) -> str:
    if limit <= 0:
        return ""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    if limit <= 1:
        return text[:limit]
    return text[: limit - 1].rstrip() + "…"
