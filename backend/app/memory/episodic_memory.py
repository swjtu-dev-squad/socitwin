from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
