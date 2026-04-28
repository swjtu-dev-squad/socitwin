from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .episodic_memory import EpisodeQuerySource


@dataclass(slots=True)
class RetrievalRequest:
    query_source: str
    query_text: str
    limit: int


class RetrievalPolicy:
    def build_request(
        self,
        *,
        topic: str = "",
        semantic_anchors: list[str] | None = None,
        entities: list[str] | None = None,
        recent_episodes: Sequence[Mapping[str, Any]] | None = None,
        limit: int,
    ) -> RetrievalRequest | None:
        normalized_topic = str(topic or "").strip()
        if normalized_topic:
            return RetrievalRequest(
                query_source=EpisodeQuerySource.DISTILLED_TOPIC.value,
                query_text=normalized_topic,
                limit=limit,
            )
        cleaned_anchors = [anchor for anchor in (semantic_anchors or []) if anchor]
        if cleaned_anchors:
            return RetrievalRequest(
                query_source=EpisodeQuerySource.STRUCTURED_EVENT_QUERY.value,
                query_text=" ".join(cleaned_anchors[:2]),
                limit=limit,
            )
        cleaned_entities = [entity for entity in (entities or []) if entity]
        if cleaned_entities:
            return RetrievalRequest(
                query_source=EpisodeQuerySource.STRUCTURED_EVENT_QUERY.value,
                query_text=" ".join(cleaned_entities[:5]),
                limit=limit,
            )
        summary_query = self._build_recent_episode_query(recent_episodes or [])
        if summary_query:
            return RetrievalRequest(
                query_source=EpisodeQuerySource.RECENT_EPISODIC_SUMMARY.value,
                query_text=summary_query,
                limit=limit,
            )
        return None

    def format_results(
        self,
        episodes: Sequence[Mapping[str, Any]],
        *,
        title: str = "Relevant long-term memory:",
    ) -> str:
        if not episodes:
            return ""

        lines = [title]
        for episode in episodes:
            if self._is_action_episode(episode):
                step_id = episode.get("step_id", "?")
                action_index = episode.get("action_index", "?")
                platform = episode.get("platform", "unknown")
                action_name = str(episode.get("action_name", "") or "")
                action_fact = str(episode.get("action_fact", "") or action_name)
                target_summary = self._extract_target_summary(episode)
                state_changes = episode.get("state_changes", []) or []
                outcome = episode.get("outcome", "")
                local_context = episode.get("local_context", {}) or {}
                idle_step_gap = int(episode.get("idle_step_gap", 0) or 0)

                lines.append(f"- Step {step_id} action {action_index} on {platform}")
                if action_name:
                    lines.append(f"  action: {action_fact}")
                if target_summary:
                    lines.append(f"  target: {target_summary}")
                parent_post = (local_context.get("parent_post") or {}).get("summary", "")
                group_summary = (local_context.get("group") or {}).get("summary", "")
                if parent_post:
                    lines.append(f"  context: parent post {parent_post}")
                elif group_summary:
                    lines.append(f"  context: group {group_summary}")
                if state_changes:
                    lines.append(
                        "  state changes: " + ", ".join(str(item) for item in state_changes)
                    )
                if outcome:
                    lines.append(f"  outcome: {outcome}")
                if idle_step_gap:
                    lines.append(f"  idle gap: {idle_step_gap} steps")
                continue

            step_id = episode.get("step_id", "?")
            platform = episode.get("platform", "unknown")
            topic = episode.get("topic", "")
            actions = episode.get("actions", []) or []
            state_changes = episode.get("state_changes", []) or []
            anchors = episode.get("semantic_anchors", []) or []
            outcome = episode.get("outcome", "")

            lines.append(f"- Step {step_id} on {platform}")
            if topic:
                lines.append(f"  topic: {topic}")
            if anchors:
                lines.append("  anchors: " + " | ".join(str(item) for item in anchors[:2]))
            if actions:
                lines.append("  actions: " + ", ".join(str(item) for item in actions))
            if state_changes:
                lines.append(
                    "  state changes: " + ", ".join(str(item) for item in state_changes)
                )
            if outcome:
                lines.append(f"  outcome: {outcome}")

        return "\n".join(lines)

    def build_reason_trace(
        self,
        episodes: Sequence[Mapping[str, Any]],
        *,
        max_chars: int = 120,
    ) -> str:
        if not episodes:
            return ""
        limit = max(1, int(max_chars))
        first = episodes[0]
        if self._is_action_episode(first):
            target_summary = self._extract_target_summary(first)
            if target_summary:
                return target_summary[:limit]
            action_fact = str(
                first.get("action_fact", "") or first.get("action_name", "")
            ).strip()
            if action_fact:
                return action_fact[:limit]

        outcome = str(first.get("outcome", "") or "").strip()
        if outcome:
            return outcome[:limit]
        anchors = [
            str(item).strip()
            for item in (first.get("semantic_anchors", []) or [])
            if str(item).strip()
        ]
        if anchors:
            return anchors[0][:limit]
        actions = [
            str(item).strip()
            for item in (first.get("actions", []) or [])
            if str(item).strip()
        ]
        if actions:
            return actions[0][:limit]
        topic = str(first.get("topic", "") or "").strip()
        return topic[:limit]

    def _build_recent_episode_query(self, episodes: Sequence[Mapping[str, Any]]) -> str:
        if not episodes:
            return ""

        parts: list[str] = []
        for episode in episodes[-2:]:
            if self._is_action_episode(episode):
                action_name = str(episode.get("action_name", "") or "").strip()
                target_summary = self._extract_target_summary(episode)
                authored_content = str(episode.get("authored_content", "") or "").strip()
                outcome = str(episode.get("outcome", "") or "").strip()
                local_context = str(
                    (episode.get("local_context") or {}).get("parent_post", {}).get(
                        "summary",
                        "",
                    )
                    or (episode.get("local_context") or {}).get("group", {}).get(
                        "summary",
                        "",
                    )
                    or ""
                ).strip()
                parts.extend(
                    item
                    for item in (
                        action_name,
                        target_summary,
                        authored_content,
                        local_context,
                        outcome,
                    )
                    if item
                )
                continue

            topic = str(episode.get("topic", "") or "").strip()
            if topic:
                parts.append(topic)
            actions = episode.get("actions", []) or []
            if actions:
                parts.extend(str(action) for action in actions[:2])
            if not topic and not actions:
                summary_text = str(episode.get("summary_text", "") or "").strip()
                outcome = str(episode.get("outcome", "") or "").strip()
                fallback_text = summary_text or outcome
                if fallback_text:
                    parts.append(fallback_text[:160])
        return " ".join(part for part in parts if part).strip()

    def _is_action_episode(self, episode: Mapping[str, Any]) -> bool:
        memory_kind = str(episode.get("memory_kind", "") or "").strip()
        return memory_kind == "action_episode" or (
            "action_name" in episode and "target_snapshot" in episode
        )

    def _extract_target_summary(self, episode: Mapping[str, Any]) -> str:
        target_snapshot = episode.get("target_snapshot", {}) or {}
        if isinstance(target_snapshot, Mapping):
            summary = str(target_snapshot.get("summary", "") or "").strip()
            if summary:
                return summary
            target_type = str(episode.get("target_type", "") or "").strip()
            target_id = episode.get("target_id")
            if target_type and target_id is not None:
                return f"{target_type}:{target_id}"
        return ""
