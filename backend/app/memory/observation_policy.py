from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .observation_semantics import (
    extract_semantic_anchors_from_snapshot,
    extract_topics_from_snapshot,
)


@dataclass(slots=True)
class PerceptionEnvelope:
    entities: list[str]
    topic: str
    snapshot: dict[str, Any]
    semantic_anchors: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)


class ObservationPolicy(ABC):
    @abstractmethod
    def build_perception_envelope(
        self,
        *,
        prompt_visible_snapshot: dict[str, Any],
        observation_prompt: str,
    ) -> PerceptionEnvelope:
        raise NotImplementedError


class DefaultObservationPolicy(ObservationPolicy):
    def build_perception_envelope(
        self,
        *,
        prompt_visible_snapshot: dict[str, Any],
        observation_prompt: str,
    ) -> PerceptionEnvelope:
        del observation_prompt
        semantic_anchors = extract_semantic_anchors_from_snapshot(prompt_visible_snapshot)
        topics = extract_topics_from_snapshot(prompt_visible_snapshot)
        return PerceptionEnvelope(
            entities=self._extract_entities_from_snapshot(prompt_visible_snapshot),
            topic=topics[0] if topics else "",
            snapshot=prompt_visible_snapshot,
            semantic_anchors=semantic_anchors,
            topics=topics,
        )

    def _extract_entities_from_snapshot(self, snapshot: dict[str, Any]) -> list[str]:
        entities: list[str] = []
        posts_payload = snapshot.get("posts") or {}
        groups_payload = snapshot.get("groups") or {}

        for post in posts_payload.get("posts", []) or []:
            post_id = post.get("post_id")
            user_id = post.get("user_id")
            if post_id is not None:
                entities.append(f"post:{post_id}")
            if user_id is not None:
                entities.append(f"user:{user_id}")
            for comment in post.get("comments", []) or []:
                comment_id = comment.get("comment_id")
                comment_user = comment.get("user_id")
                if comment_id is not None:
                    entities.append(f"comment:{comment_id}")
                if comment_user is not None:
                    entities.append(f"user:{comment_user}")

        for group in groups_payload.get("all_groups", []) or []:
            if not isinstance(group, dict):
                continue
            group_id = group.get("group_id")
            if group_id is not None:
                entities.append(f"group:{group_id}")
        for message in groups_payload.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            message_id = message.get("message_id")
            group_id = message.get("group_id")
            user_id = message.get("user_id")
            if message_id is not None:
                entities.append(f"group_message:{message_id}")
            if group_id is not None:
                entities.append(f"group:{group_id}")
            if user_id is not None:
                entities.append(f"user:{user_id}")

        return list(dict.fromkeys(entities))
