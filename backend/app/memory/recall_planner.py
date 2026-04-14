from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from .config import ActionV1RuntimeSettings
from .retrieval_policy import RetrievalPolicy
from .working_memory import MemoryState, recent_action_seed_payloads, recent_action_target_refs


class LongtermStoreLike(Protocol):
    def retrieve_relevant(
        self,
        query_text: str,
        *,
        limit: int,
        agent_id: str | int | None = None,
    ) -> list[dict[str, Any]]:
        ...


@dataclass(slots=True)
class RecallRuntimeState:
    last_successful_query_source: str = ""
    last_successful_query_text: str = ""
    last_successful_step_id: int | None = None
    last_recalled_count: int = 0
    last_recalled_step_ids: list[int] = field(default_factory=list)
    last_injected_count: int = 0
    last_injected_step_ids: list[int] = field(default_factory=list)
    last_injected_action_keys: list[tuple[int, int]] = field(default_factory=list)
    last_reason_trace: str = ""


@dataclass(slots=True)
class RecallPreparation:
    query_source: str = ""
    query_text: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    recalled_count: int = 0
    recalled_step_ids: list[int] = field(default_factory=list)
    retrieval_attempted: bool = False
    clear_anchor: bool = False
    gate_decision: bool = False
    gate_reason_flags: dict[str, bool] = field(default_factory=dict)


class RecallPlanner:
    def __init__(
        self,
        runtime_settings: ActionV1RuntimeSettings,
        retrieval_policy: RetrievalPolicy,
    ) -> None:
        self.runtime_settings = runtime_settings
        self.retrieval_policy = retrieval_policy

    def prepare(
        self,
        *,
        agent_id: str | int | None = None,
        topic: str = "",
        semantic_anchors: list[str] | None = None,
        entities: list[str] | None = None,
        snapshot: Mapping[str, Any] | None = None,
        memory_state: MemoryState,
        longterm_store: LongtermStoreLike | None,
        next_step_id: int,
        runtime_state: RecallRuntimeState,
    ) -> RecallPreparation:
        if longterm_store is None:
            return RecallPreparation(clear_anchor=True)

        request = self.retrieval_policy.build_request(
            topic=topic,
            semantic_anchors=semantic_anchors or [],
            entities=entities or [],
            recent_episodes=recent_action_seed_payloads(memory_state.recent.segments[-2:])[-4:],
            limit=self.runtime_settings.recall_preset.retrieval_limit,
        )
        gate_decision, gate_reason_flags = self._should_retrieve(
            request=request,
            topic=topic,
            semantic_anchors=semantic_anchors or [],
            entities=entities or [],
            snapshot=snapshot or {},
            memory_state=memory_state,
            next_step_id=next_step_id,
            runtime_state=runtime_state,
        )
        if not gate_decision:
            return RecallPreparation(
                gate_decision=False,
                gate_reason_flags=gate_reason_flags,
            )

        episodes = list(
            longterm_store.retrieve_relevant(
                request.query_text,
                limit=request.limit,
                agent_id=agent_id,
            )
        )
        return RecallPreparation(
            query_source=request.query_source,
            query_text=request.query_text,
            candidates=episodes,
            recalled_count=len(episodes),
            recalled_step_ids=[
                int(step_id)
                for step_id in (episode.get("step_id") for episode in episodes)
                if isinstance(step_id, int)
            ],
            retrieval_attempted=True,
            gate_decision=True,
            gate_reason_flags=gate_reason_flags,
        )

    def commit_selection(
        self,
        *,
        runtime_state: RecallRuntimeState,
        preparation: RecallPreparation,
        selected_items: list[Mapping[str, Any]],
        step_id: int,
    ) -> None:
        if preparation.clear_anchor:
            runtime_state.last_successful_query_source = ""
            runtime_state.last_successful_query_text = ""
            runtime_state.last_successful_step_id = None
            runtime_state.last_recalled_count = 0
            runtime_state.last_recalled_step_ids = []
            runtime_state.last_injected_count = 0
            runtime_state.last_injected_step_ids = []
            runtime_state.last_injected_action_keys = []
            runtime_state.last_reason_trace = ""
            return

        runtime_state.last_recalled_count = (
            preparation.recalled_count if preparation.retrieval_attempted else 0
        )
        runtime_state.last_recalled_step_ids = (
            list(preparation.recalled_step_ids) if preparation.retrieval_attempted else []
        )
        runtime_state.last_injected_count = len(selected_items)
        runtime_state.last_injected_step_ids = [
            int(item["step_id"])
            for item in selected_items
            if isinstance(item.get("step_id"), int)
        ]
        runtime_state.last_injected_action_keys = [
            (int(item["step_id"]), int(item["action_index"]))
            for item in selected_items
            if self._is_action_episode(item)
            and isinstance(item.get("step_id"), int)
            and isinstance(item.get("action_index"), int)
        ]
        runtime_state.last_reason_trace = self.retrieval_policy.build_reason_trace(
            selected_items,
            max_chars=self.runtime_settings.recall_preset.max_reason_trace_chars,
        )
        if selected_items:
            runtime_state.last_successful_query_source = preparation.query_source
            runtime_state.last_successful_query_text = preparation.query_text
            runtime_state.last_successful_step_id = step_id

    def _should_retrieve(
        self,
        *,
        request: Any,
        topic: str,
        semantic_anchors: list[str],
        entities: list[str],
        snapshot: Mapping[str, Any],
        memory_state: MemoryState,
        next_step_id: int,
        runtime_state: RecallRuntimeState,
    ) -> tuple[bool, dict[str, bool]]:
        if request is None:
            return False, {}
        query_text = str(request.query_text or "").strip()
        if not query_text:
            return False, {}

        preset = self.runtime_settings.recall_preset
        topic_trigger = preset.allow_topic_trigger and bool(str(topic or "").strip())
        anchor_trigger = preset.allow_anchor_trigger and bool(semantic_anchors)
        recent_action_trigger = preset.allow_recent_action_trigger and self._recent_action_rehit(
            snapshot=snapshot,
            memory_state=memory_state,
        )
        self_authored_trigger = (
            preset.allow_self_authored_trigger
            and self._snapshot_has_self_authored_content(snapshot)
        )
        has_primary_trigger = (
            topic_trigger
            or anchor_trigger
            or recent_action_trigger
            or self_authored_trigger
        )
        entity_trigger = (
            preset.min_trigger_entity_count > 0
            and len(entities) >= preset.min_trigger_entity_count
            and not has_primary_trigger
        )
        has_strong_trigger = has_primary_trigger or entity_trigger
        gate_reason_flags = {
            "topic_trigger": bool(topic_trigger),
            "anchor_trigger": bool(anchor_trigger),
            "recent_action_trigger": bool(recent_action_trigger),
            "self_authored_trigger": bool(self_authored_trigger),
            "entity_trigger": bool(entity_trigger),
            "cooldown_blocked": False,
            "repeated_query_blocked": False,
        }

        last_successful_step_id = runtime_state.last_successful_step_id
        if last_successful_step_id is None:
            return has_strong_trigger, gate_reason_flags

        steps_since_last_recall = next_step_id - last_successful_step_id
        repeated_query = query_text == str(runtime_state.last_successful_query_text or "").strip()
        if (
            repeated_query
            and steps_since_last_recall
            <= preset.deny_repeated_query_within_steps
        ):
            gate_reason_flags["repeated_query_blocked"] = True
            return False, gate_reason_flags
        if steps_since_last_recall <= preset.cooldown_steps and not has_strong_trigger:
            gate_reason_flags["cooldown_blocked"] = True
            return False, gate_reason_flags
        return has_strong_trigger, gate_reason_flags

    def _recent_action_rehit(
        self,
        *,
        snapshot: Mapping[str, Any],
        memory_state: MemoryState,
    ) -> bool:
        visible_entities: set[str] = set()
        posts_payload = snapshot.get("posts", {}) or {}
        for post in posts_payload.get("posts", []) or []:
            post_id = post.get("post_id")
            user_id = post.get("user_id")
            if post_id is not None:
                visible_entities.add(f"post:{post_id}")
            if user_id is not None:
                visible_entities.add(f"user:{user_id}")
            for comment in post.get("comments", []) or []:
                comment_id = comment.get("comment_id")
                comment_user = comment.get("user_id")
                if comment_id is not None:
                    visible_entities.add(f"comment:{comment_id}")
                if comment_user is not None:
                    visible_entities.add(f"user:{comment_user}")

        groups_payload = snapshot.get("groups", {}) or {}
        for group in groups_payload.get("all_groups", []) or []:
            if not isinstance(group, dict):
                continue
            group_id = group.get("group_id")
            if group_id is not None:
                visible_entities.add(f"group:{group_id}")
        for message in groups_payload.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            message_id = message.get("message_id")
            group_id = message.get("group_id")
            user_id = message.get("user_id")
            if message_id is not None:
                visible_entities.add(f"group_message:{message_id}")
            if group_id is not None:
                visible_entities.add(f"group:{group_id}")
            if user_id is not None:
                visible_entities.add(f"user:{user_id}")

        for target_ref in recent_action_target_refs(memory_state.recent.segments[-2:]):
            if target_ref in visible_entities:
                return True
        return False

    def _snapshot_has_self_authored_content(self, snapshot: Mapping[str, Any]) -> bool:
        posts_payload = snapshot.get("posts", {}) or {}
        for post in posts_payload.get("posts", []) or []:
            if str(post.get("relation_anchor", "") or "") == "self_authored":
                return True
            for comment in post.get("comments", []) or []:
                if str(comment.get("relation_anchor", "") or "") == "self_authored":
                    return True

        groups_payload = snapshot.get("groups", {}) or {}
        for message in groups_payload.get("messages", []) or []:
            if str(message.get("relation_anchor", "") or "") == "self_authored":
                return True
        return False

    def _is_action_episode(self, item: Mapping[str, Any]) -> bool:
        return str(item.get("memory_kind", "") or "") == "action_episode"
