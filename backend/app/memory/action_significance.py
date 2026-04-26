from __future__ import annotations

HIGH_SIGNIFICANCE_ACTIONS = {
    "create_post",
    "create_comment",
    "send_to_group",
    "create_group",
}
MEDIUM_SIGNIFICANCE_ACTIONS = {
    "follow",
    "unfollow",
    "mute",
    "unmute",
    "join_group",
    "leave_group",
    "repost",
    "report_post",
}
LOW_SIGNIFICANCE_ACTIONS = {
    "like_post",
    "unlike_post",
    "dislike_post",
    "undo_dislike_post",
    "like_comment",
    "unlike_comment",
    "dislike_comment",
    "undo_dislike_comment",
}


def infer_action_significance(*, action_name: str, authored_content: str) -> str:
    normalized_name = str(action_name or "").strip()
    normalized_authored = str(authored_content or "").strip()
    if normalized_name == "quote_post":
        return "high" if normalized_authored else "medium"
    if normalized_name in HIGH_SIGNIFICANCE_ACTIONS:
        return "high"
    if normalized_name in MEDIUM_SIGNIFICANCE_ACTIONS:
        return "medium"
    if normalized_name in LOW_SIGNIFICANCE_ACTIONS:
        return "low"
    return "medium" if normalized_authored else "low"


def normalize_execution_status(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"success", "failed", "hallucinated", "unknown"}:
        return normalized
    return "unknown"


def is_memory_worthy_action(
    *,
    execution_status: str,
    action_significance: str,
) -> bool:
    if normalize_execution_status(execution_status) == "hallucinated":
        return False
    return str(action_significance or "").strip().lower() in {"medium", "high"}
