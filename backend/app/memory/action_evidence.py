from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .action_capabilities import ActionCapabilityRegistry
from .action_significance import normalize_execution_status


NOT_FOUND_PATTERNS = (
    "not found",
    "no such",
    "does not exist",
    "missing",
)


@dataclass(slots=True)
class ActionEvidence:
    action_name: str
    eligible_for_longterm: bool = False
    target_type: str = ""
    target_id: Any = None
    target_snapshot: dict[str, Any] = field(default_factory=dict)
    target_visible_in_prompt: bool = False
    target_resolution_status: str = ""
    execution_status: str = ""
    local_context: dict[str, Any] = field(default_factory=dict)
    authored_content: str = ""

    def to_metadata_dict(self) -> dict[str, Any]:
        return asdict(self)


class ActionEvidenceBuilder:
    def __init__(self, registry: ActionCapabilityRegistry | None = None) -> None:
        self.registry = registry or ActionCapabilityRegistry()

    def build(
        self,
        *,
        prompt_visible_snapshot: dict[str, Any],
        action_name: str,
        tool_args: dict[str, Any],
        tool_result: Any,
    ) -> ActionEvidence:
        target_type, target_id = self._infer_target_reference(
            action_name=action_name,
            tool_args=tool_args,
        )
        target_snapshot = self._resolve_target_snapshot(
            prompt_visible_snapshot=prompt_visible_snapshot,
            target_type=target_type,
            target_id=target_id,
        )
        target_visible = bool(target_snapshot)
        return ActionEvidence(
            action_name=action_name,
            eligible_for_longterm=self.registry.is_eligible_for_longterm(action_name),
            target_type=target_type,
            target_id=target_id,
            target_snapshot=target_snapshot,
            target_visible_in_prompt=target_visible,
            target_resolution_status=self._build_resolution_status(
                target_visible=target_visible,
                tool_result=tool_result,
            ),
            execution_status=self._build_execution_status(
                target_visible=target_visible,
                tool_result=tool_result,
            ),
            local_context=self._build_local_context(
                prompt_visible_snapshot=prompt_visible_snapshot,
                target_type=target_type,
                target_id=target_id,
                target_snapshot=target_snapshot,
            ),
            authored_content=self.registry.extract_authored_content(
                action_name=action_name,
                tool_args=tool_args,
            ),
        )

    def _infer_target_reference(
        self,
        *,
        action_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[str, Any]:
        return self.registry.infer_target_reference(
            action_name=action_name,
            tool_args=tool_args,
        )

    def _resolve_target_snapshot(
        self,
        *,
        prompt_visible_snapshot: dict[str, Any],
        target_type: str,
        target_id: Any,
    ) -> dict[str, Any]:
        if not target_type:
            return {}
        if target_type == "post":
            for post in ((prompt_visible_snapshot.get("posts") or {}).get("posts", []) or []):
                if post.get("post_id") == target_id:
                    return dict(post)
            return {}
        if target_type == "comment":
            for post in ((prompt_visible_snapshot.get("posts") or {}).get("posts", []) or []):
                for comment in post.get("comments", []) or []:
                    if comment.get("comment_id") == target_id:
                        return dict(comment)
            return {}
        if target_type == "group":
            groups_payload = prompt_visible_snapshot.get("groups") or {}
            for group in groups_payload.get("all_groups", []) or []:
                if group.get("group_id") == target_id:
                    return dict(group)
            if target_id in (groups_payload.get("joined_group_ids") or []):
                return {
                    "object_kind": "group",
                    "group_id": target_id,
                    "relation_anchor": "unknown",
                    "self_authored": False,
                    "summary": "",
                    "evidence_quality": "missing",
                    "degraded_evidence": True,
                }
            return {}
        return {}

    def _build_local_context(
        self,
        *,
        prompt_visible_snapshot: dict[str, Any],
        target_type: str,
        target_id: Any,
        target_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        if target_type == "comment":
            for post in ((prompt_visible_snapshot.get("posts") or {}).get("posts", []) or []):
                for comment in post.get("comments", []) or []:
                    if comment.get("comment_id") == target_id:
                        return {
                            "parent_post": {
                                "post_id": post.get("post_id"),
                                "summary": post.get("summary", ""),
                                "relation_anchor": post.get("relation_anchor", "unknown"),
                                "self_authored": bool(post.get("self_authored", False)),
                            }
                        }
            return {}
        if target_type == "post" and target_snapshot:
            visible_comments = [
                {
                    "comment_id": comment.get("comment_id"),
                    "summary": comment.get("summary", ""),
                    "self_authored": bool(comment.get("self_authored", False)),
                }
                for comment in (target_snapshot.get("comments", []) or [])[:2]
            ]
            return {"visible_comments": visible_comments} if visible_comments else {}
        if target_type == "group":
            groups_payload = prompt_visible_snapshot.get("groups") or {}
            visible_messages = [
                {
                    "message_id": message.get("message_id"),
                    "summary": message.get("summary", ""),
                }
                for message in groups_payload.get("messages", []) or []
                if message.get("group_id") == target_id
            ][:2]
            if target_snapshot or visible_messages:
                return {
                    "group": {
                        "group_id": target_id,
                        "summary": target_snapshot.get("summary", ""),
                        "relation_anchor": target_snapshot.get("relation_anchor", "unknown"),
                        "self_authored": bool(target_snapshot.get("self_authored", False)),
                    },
                    "visible_messages": visible_messages,
                }
            return {}
        return {}

    def _build_resolution_status(
        self,
        *,
        target_visible: bool,
        tool_result: Any,
    ) -> str:
        if target_visible:
            if self._tool_result_indicates_not_found(tool_result):
                return "expired_target"
            return "visible_in_prompt"
        if self._tool_result_indicates_not_found(tool_result):
            return "invalid_target"
        return "not_visible_in_prompt"

    def _build_execution_status(
        self,
        *,
        target_visible: bool,
        tool_result: Any,
    ) -> str:
        if isinstance(tool_result, dict):
            success = tool_result.get("success")
            if success is True:
                return "success"
            if self._tool_result_indicates_not_found(tool_result):
                return "failed" if target_visible else "hallucinated"
            if success is False:
                return "failed"
        return normalize_execution_status("")

    def _tool_result_indicates_not_found(self, tool_result: Any) -> bool:
        if isinstance(tool_result, dict):
            candidates = [
                str(tool_result.get("message", "") or ""),
                str(tool_result.get("error", "") or ""),
                str(tool_result.get("result", "") or ""),
            ]
            lowered = " ".join(candidates).lower()
            return any(pattern in lowered for pattern in NOT_FOUND_PATTERNS)
        return False
