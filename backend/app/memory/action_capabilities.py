from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActionCapability:
    name: str
    eligible_for_longterm: bool = False
    action_category: str = "unknown"
    target_refs: tuple[tuple[str, str], ...] = ()
    authored_content_key: str = ""
    fallback_target_type: str = ""


DEFAULT_ACTION_CAPABILITY = ActionCapability(name="")


class ActionCapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities = {
            capability.name: capability for capability in _default_capabilities()
        }

    def get(self, action_name: str) -> ActionCapability:
        return self._capabilities.get(action_name, DEFAULT_ACTION_CAPABILITY)

    def is_eligible_for_longterm(self, action_name: str) -> bool:
        return self.get(action_name).eligible_for_longterm

    def action_category(self, action_name: str) -> str:
        return self.get(action_name).action_category or "unknown"

    def infer_target_reference(
        self,
        *,
        action_name: str,
        tool_args: dict[str, Any],
    ) -> tuple[str, Any]:
        capability = self.get(action_name)
        for arg_name, target_type in capability.target_refs:
            if arg_name in tool_args:
                return target_type, tool_args.get(arg_name)
        if capability.fallback_target_type:
            return capability.fallback_target_type, None
        return "", None

    def extract_authored_content(
        self,
        *,
        action_name: str,
        tool_args: dict[str, Any],
    ) -> str:
        key = self.get(action_name).authored_content_key
        if not key:
            return ""
        return str(tool_args.get(key, "") or "")


def _default_capabilities() -> list[ActionCapability]:
    return [
        ActionCapability(
            name="like_post",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("post_id", "post"),),
        ),
        ActionCapability(
            name="unlike_post",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("post_id", "post"),),
        ),
        ActionCapability(
            name="dislike_post",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("post_id", "post"),),
        ),
        ActionCapability(
            name="undo_dislike_post",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("post_id", "post"),),
        ),
        ActionCapability(
            name="report_post",
            eligible_for_longterm=True,
            action_category="moderation",
            target_refs=(("post_id", "post"),),
        ),
        ActionCapability(
            name="repost",
            eligible_for_longterm=True,
            action_category="content_propagation",
            target_refs=(("post_id", "post"),),
        ),
        ActionCapability(
            name="quote_post",
            eligible_for_longterm=True,
            action_category="content_propagation",
            target_refs=(("post_id", "post"),),
            authored_content_key="quote_content",
        ),
        ActionCapability(
            name="create_post",
            eligible_for_longterm=True,
            action_category="authored_content",
            authored_content_key="content",
        ),
        ActionCapability(
            name="create_comment",
            eligible_for_longterm=True,
            action_category="authored_content",
            target_refs=(("comment_id", "comment"), ("post_id", "post")),
            authored_content_key="content",
        ),
        ActionCapability(
            name="like_comment",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("comment_id", "comment"),),
        ),
        ActionCapability(
            name="unlike_comment",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("comment_id", "comment"),),
        ),
        ActionCapability(
            name="dislike_comment",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("comment_id", "comment"),),
        ),
        ActionCapability(
            name="undo_dislike_comment",
            eligible_for_longterm=True,
            action_category="content_preference",
            target_refs=(("comment_id", "comment"),),
        ),
        ActionCapability(
            name="follow",
            eligible_for_longterm=True,
            action_category="relationship_change",
            target_refs=(("followee_id", "user"), ("user_id", "user")),
        ),
        ActionCapability(
            name="unfollow",
            eligible_for_longterm=True,
            action_category="relationship_change",
            target_refs=(("followee_id", "user"), ("user_id", "user")),
        ),
        ActionCapability(
            name="mute",
            eligible_for_longterm=True,
            action_category="relationship_change",
            target_refs=(("mutee_id", "user"), ("user_id", "user")),
        ),
        ActionCapability(
            name="unmute",
            eligible_for_longterm=True,
            action_category="relationship_change",
            target_refs=(("mutee_id", "user"), ("user_id", "user")),
        ),
        ActionCapability(
            name="join_group",
            eligible_for_longterm=True,
            action_category="group_membership",
            target_refs=(("group_id", "group"),),
        ),
        ActionCapability(
            name="leave_group",
            eligible_for_longterm=True,
            action_category="group_membership",
            target_refs=(("group_id", "group"),),
        ),
        ActionCapability(
            name="send_to_group",
            eligible_for_longterm=True,
            action_category="group_authored_content",
            target_refs=(("group_id", "group"),),
            authored_content_key="message",
        ),
        ActionCapability(
            name="create_group",
            eligible_for_longterm=True,
            action_category="group_creation",
            authored_content_key="group_name",
            fallback_target_type="group",
        ),
    ]
