from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .action_capabilities import ActionCapabilityRegistry
from .action_significance import infer_action_significance
from .longterm import episode_to_payload


class StepRecordKind(str, Enum):
    PERCEPTION = "perception"
    DECISION = "decision"
    ACTION_RESULT = "action_result"
    FINAL_OUTCOME = "final_outcome"
    REASONING_NOISE = "reasoning_noise"


class EpisodeQuerySource(str, Enum):
    DISTILLED_TOPIC = "distilled_topic"
    RECENT_EPISODIC_SUMMARY = "recent_episodic_summary"
    STRUCTURED_EVENT_QUERY = "structured_event_query"


@dataclass(slots=True)
class StepRecord:
    role: str
    kind: StepRecordKind
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StepSegment:
    agent_id: str
    step_id: int
    timestamp: float
    platform: str
    records: list[StepRecord] = field(default_factory=list)

    def records_by_kind(self, kind: StepRecordKind) -> list[StepRecord]:
        return [record for record in self.records if record.kind == kind]

    @property
    def perception_records(self) -> list[StepRecord]:
        return self.records_by_kind(StepRecordKind.PERCEPTION)

    @property
    def decision_records(self) -> list[StepRecord]:
        return self.records_by_kind(StepRecordKind.DECISION)

    @property
    def action_result_records(self) -> list[StepRecord]:
        return self.records_by_kind(StepRecordKind.ACTION_RESULT)

    @property
    def final_outcome_records(self) -> list[StepRecord]:
        return self.records_by_kind(StepRecordKind.FINAL_OUTCOME)

    @property
    def reasoning_noise_records(self) -> list[StepRecord]:
        return self.records_by_kind(StepRecordKind.REASONING_NOISE)


@dataclass(slots=True)
class EpisodeRecord:
    agent_id: str
    step_id: int
    timestamp: float
    platform: str
    observed_entities: list[str] = field(default_factory=list)
    semantic_anchors: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    state_changes: list[str] = field(default_factory=list)
    outcome: str = ""
    topic: str = ""
    query_source: str = ""
    query_hint: str = ""
    notes: list[str] = field(default_factory=list)

    def to_summary_lines(self) -> list[str]:
        lines = [f"Episode summary for step {self.step_id} on {self.platform}."]
        if self.observed_entities:
            lines.append("Observed: " + ", ".join(self.observed_entities))
        if self.semantic_anchors:
            lines.append("Anchors: " + " | ".join(self.semantic_anchors))
        if self.actions:
            lines.append("Actions: " + ", ".join(self.actions))
        if self.state_changes:
            lines.append("State changes: " + ", ".join(self.state_changes))
        if self.outcome:
            lines.append("Outcome: " + self.outcome)
        if self.notes:
            lines.append("Notes: " + "; ".join(self.notes))
        return lines

    def to_summary_text(self) -> str:
        return "\n".join(self.to_summary_lines())


@dataclass(slots=True)
class ActionEpisode:
    agent_id: str
    step_id: int
    action_index: int
    timestamp: float
    platform: str
    action_name: str
    action_category: str = "unknown"
    action_fact: str = ""
    target_type: str = ""
    target_id: Any = None
    target_snapshot: dict[str, Any] = field(default_factory=dict)
    target_visible_in_prompt: bool = False
    target_resolution_status: str = ""
    execution_status: str = ""
    local_context: dict[str, Any] = field(default_factory=dict)
    authored_content: str = ""
    state_changes: list[str] = field(default_factory=list)
    outcome: str = ""
    idle_step_gap: int = 0
    topic: str = ""
    query_source: str = ""
    evidence_quality: str = ""
    degraded_evidence: bool = False
    action_significance: str = ""

    def to_payload(self) -> dict[str, Any]:
        return episode_to_payload(
            {
                "memory_kind": "action_episode",
                "agent_id": self.agent_id,
                "step_id": self.step_id,
                "action_index": self.action_index,
                "timestamp": self.timestamp,
                "platform": self.platform,
                "action_name": self.action_name,
                "action_category": self.action_category,
                "action_fact": self.action_fact,
                "target_type": self.target_type,
                "target_id": self.target_id,
                "target_snapshot": self.target_snapshot,
                "target_visible_in_prompt": self.target_visible_in_prompt,
                "target_resolution_status": self.target_resolution_status,
                "execution_status": self.execution_status,
                "local_context": self.local_context,
                "authored_content": self.authored_content,
                "state_changes": self.state_changes,
                "outcome": self.outcome,
                "idle_step_gap": self.idle_step_gap,
                "topic": self.topic,
                "query_source": self.query_source,
                "action_significance": self.action_significance,
                "evidence_quality": self.evidence_quality,
                "degraded_evidence": self.degraded_evidence,
                "summary_text": "",
                "metadata": {},
            }
        )


@dataclass(slots=True)
class HeartbeatRange:
    agent_id: str
    start_step: int
    end_step: int
    count: int
    start_timestamp: float
    end_timestamp: float
    first_digest: str = ""
    last_digest: str = ""
    sampled_entities: list[str] = field(default_factory=list)

    def covers_step(self, step_id: int) -> bool:
        return self.start_step <= step_id <= self.end_step

    def to_summary_text(self) -> str:
        if self.start_step == self.end_step:
            line = f"Step {self.start_step}: no eligible actions."
        else:
            line = f"Steps {self.start_step}-{self.end_step}: no eligible actions."
        details: list[str] = []
        if self.first_digest:
            details.append(f"first={self.first_digest}")
        if self.last_digest and self.last_digest != self.first_digest:
            details.append(f"last={self.last_digest}")
        if self.sampled_entities:
            details.append("entities=" + "|".join(self.sampled_entities))
        if details:
            line += " " + "; ".join(details)
        return line


class PlatformMemoryAdapter:
    def __init__(self) -> None:
        self.action_capability_registry = ActionCapabilityRegistry()

    def extract_observed_entities(self, segment: StepSegment) -> list[str]:
        entities: list[str] = []
        for record in segment.perception_records:
            entities.extend(record.metadata.get("entities", []))
        return list(dict.fromkeys(item for item in entities if item))

    def extract_actions(self, segment: StepSegment) -> list[str]:
        actions: list[str] = []
        for record in segment.decision_records + segment.action_result_records:
            action = record.metadata.get("action")
            if action:
                actions.append(str(action))
        return list(dict.fromkeys(actions))

    def extract_state_changes(self, segment: StepSegment) -> list[str]:
        changes: list[str] = []
        for record in segment.action_result_records:
            changes.extend(record.metadata.get("state_changes", []))
        return list(dict.fromkeys(item for item in changes if item))

    def extract_outcome(self, segment: StepSegment) -> str:
        outcomes = [
            record.content.strip()
            for record in segment.final_outcome_records
            if record.content.strip()
        ]
        if outcomes:
            return outcomes[-1]
        outcomes = [
            record.content.strip()
            for record in segment.action_result_records
            if record.content.strip()
        ]
        if outcomes:
            return outcomes[-1]
        decisions = [
            record.content.strip()
            for record in segment.decision_records
            if record.content.strip()
        ]
        return decisions[-1] if decisions else ""

    def extract_topic(self, segment: StepSegment) -> str:
        for record in segment.perception_records:
            topic = record.metadata.get("topic")
            if topic:
                return str(topic)
        return ""

    def build_episode_record(self, segment: StepSegment) -> EpisodeRecord:
        return EpisodeRecord(
            agent_id=segment.agent_id,
            step_id=segment.step_id,
            timestamp=segment.timestamp,
            platform=segment.platform,
            observed_entities=self.extract_observed_entities(segment),
            semantic_anchors=self.extract_semantic_anchors(segment),
            actions=self.extract_actions(segment),
            state_changes=self.extract_state_changes(segment),
            outcome=self.extract_outcome(segment),
            topic=self.extract_topic(segment),
            query_source=self.extract_query_source(segment),
            query_hint=self.extract_query_hint(segment),
            notes=self.extract_notes(segment),
        )

    def build_action_episodes(self, segment: StepSegment) -> list[ActionEpisode]:
        action_episodes: list[ActionEpisode] = []
        outcome = self.extract_outcome(segment)
        action_results_by_tool_call_id = {
            str(record.metadata.get("tool_call_id", "") or ""): record
            for record in segment.action_result_records
            if record.metadata.get("tool_call_id")
        }
        for index, decision in enumerate(segment.decision_records):
            action_name = str(decision.metadata.get("action_name", "") or "")
            evidence_metadata = decision.metadata.get("action_evidence", {}) or {}
            eligible_for_longterm = bool(
                evidence_metadata.get(
                    "eligible_for_longterm",
                    self.action_capability_registry.is_eligible_for_longterm(action_name),
                )
            )
            if not eligible_for_longterm:
                continue
            tool_call_id = str(decision.metadata.get("tool_call_id", "") or "")
            action_result = (
                action_results_by_tool_call_id.get(tool_call_id) if tool_call_id else None
            )
            if action_result is None and not tool_call_id:
                action_result = (
                    segment.action_result_records[index]
                    if index < len(segment.action_result_records)
                    else None
                )
            evidence = (
                (action_result.metadata.get("action_evidence", {}) if action_result else {})
                or decision.metadata.get("action_evidence", {})
            )
            target_snapshot = dict(evidence.get("target_snapshot", {}) or {})
            authored_content = str(evidence.get("authored_content", "") or "")
            action_episodes.append(
                ActionEpisode(
                    agent_id=segment.agent_id,
                    step_id=segment.step_id,
                    action_index=index,
                    timestamp=segment.timestamp,
                    platform=segment.platform,
                    action_name=action_name,
                    action_category=self.action_capability_registry.action_category(
                        action_name
                    ),
                    action_fact=str(decision.metadata.get("action", decision.content) or ""),
                    target_type=str(evidence.get("target_type", "") or ""),
                    target_id=evidence.get("target_id"),
                    target_snapshot=target_snapshot,
                    target_visible_in_prompt=bool(
                        evidence.get("target_visible_in_prompt", False)
                    ),
                    target_resolution_status=str(
                        evidence.get("target_resolution_status", "") or ""
                    ),
                    execution_status=str(evidence.get("execution_status", "") or ""),
                    local_context=dict(evidence.get("local_context", {}) or {}),
                    authored_content=authored_content,
                    state_changes=list(
                        (action_result.metadata.get("state_changes", []) if action_result else [])
                        or []
                    ),
                    outcome=outcome,
                    topic=self.extract_topic(segment),
                    query_source=self.extract_query_source(segment),
                    evidence_quality=str(target_snapshot.get("evidence_quality", "") or ""),
                    degraded_evidence=bool(target_snapshot.get("degraded_evidence", False)),
                    action_significance=infer_action_significance(
                        action_name=action_name,
                        authored_content=authored_content,
                    ),
                )
            )
        return action_episodes

    def extract_query_source(self, segment: StepSegment) -> str:
        topic = self.extract_topic(segment).strip()
        if topic:
            return EpisodeQuerySource.DISTILLED_TOPIC.value
        if self.extract_actions(segment) or self.extract_observed_entities(segment):
            return EpisodeQuerySource.STRUCTURED_EVENT_QUERY.value
        return EpisodeQuerySource.RECENT_EPISODIC_SUMMARY.value

    def extract_query_hint(self, segment: StepSegment) -> str:
        parts: list[str] = []
        topic = self.extract_topic(segment).strip()
        actions = self.extract_actions(segment)
        entities = self.extract_observed_entities(segment)
        anchors = self.extract_semantic_anchors(segment)
        if topic:
            parts.append(f"topic:{topic}")
        if actions:
            parts.append("actions:" + "|".join(actions[:2]))
        if entities:
            parts.append("entities:" + "|".join(entities[:3]))
        if anchors:
            parts.append("anchors:" + " || ".join(anchors[:2]))
        return " ; ".join(parts)

    def extract_semantic_anchors(self, segment: StepSegment) -> list[str]:
        anchors: list[str] = []
        for record in segment.perception_records:
            anchors.extend(record.metadata.get("semantic_anchors", []))
        return list(dict.fromkeys(item for item in anchors if item))[:4]

    def extract_notes(self, segment: StepSegment) -> list[str]:
        notes = [
            f"perception_count={len(segment.perception_records)}",
            f"decision_count={len(segment.decision_records)}",
            f"action_result_count={len(segment.action_result_records)}",
            f"final_outcome_count={len(segment.final_outcome_records)}",
        ]
        if segment.reasoning_noise_records:
            notes.append(f"reasoning_noise_count={len(segment.reasoning_noise_records)}")
        return notes


class DefaultPlatformMemoryAdapter(PlatformMemoryAdapter):
    pass


class RedditMemoryAdapter(DefaultPlatformMemoryAdapter):
    pass


class TwitterMemoryAdapter(DefaultPlatformMemoryAdapter):
    pass


def build_platform_memory_adapter(platform: str) -> PlatformMemoryAdapter:
    normalized = platform.lower()
    if normalized == "reddit":
        return RedditMemoryAdapter()
    if normalized == "twitter":
        return TwitterMemoryAdapter()
    return DefaultPlatformMemoryAdapter()
