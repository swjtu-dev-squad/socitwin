from __future__ import annotations

import re
from typing import Any

WHITESPACE_RE = re.compile(r"\s+")


def summarize_text(value: Any, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    text = WHITESPACE_RE.sub(" ", value).strip()
    if not text:
        return ""
    if text.startswith("[truncated from ") and text.endswith(" chars]"):
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def infer_evidence_quality(value: Any) -> tuple[str, bool]:
    if not isinstance(value, str):
        return "missing", True
    text = value.strip()
    if not text:
        return "missing", True
    if text.startswith("[truncated from ") and text.endswith(" chars]"):
        return "omitted", True
    if "...[summarized from " in text or "...[compacted from " in text or "...[truncated " in text:
        return "degraded", True
    return "normal", False


def infer_self_authored(*, object_user_id: Any, current_agent_id: Any) -> bool:
    if object_user_id is None or current_agent_id is None:
        return False
    return str(object_user_id) == str(current_agent_id)


def build_prompt_posts_view(posts: list[dict]) -> list[dict]:
    prompt_posts: list[dict] = []
    for post in posts:
        prompt_post = dict(post)
        if isinstance(prompt_post.get("content"), str):
            prompt_post["content_summary"] = summarize_text(prompt_post["content"], 120)
        prompt_comments: list[dict] = []
        for comment in prompt_post.get("comments", []) or []:
            prompt_comment = dict(comment)
            if isinstance(prompt_comment.get("content"), str):
                prompt_comment["content_summary"] = summarize_text(
                    prompt_comment["content"], 96
                )
            prompt_comments.append(prompt_comment)
        prompt_post["comments"] = prompt_comments
        prompt_posts.append(prompt_post)
    return prompt_posts


def build_prompt_visible_posts_snapshot(
    posts_payload: dict[str, Any],
    *,
    current_agent_id: Any = None,
) -> dict[str, Any]:
    prompt_posts: list[dict[str, Any]] = []
    for post in posts_payload.get("posts", []) or []:
        quality, degraded = infer_evidence_quality(post.get("content"))
        prompt_post = {
            "object_kind": "post",
            "post_id": post.get("post_id"),
            "user_id": post.get("user_id"),
            "relation_anchor": "unknown",
            "self_authored": infer_self_authored(
                object_user_id=post.get("user_id"),
                current_agent_id=current_agent_id,
            ),
            "summary": summarize_text(post.get("content_summary") or post.get("content"), 120),
            "evidence_quality": quality,
            "degraded_evidence": degraded,
            "comments_omitted_count": int(post.get("comments_omitted_count", 0) or 0),
            "comments": [],
        }
        for comment in post.get("comments", []) or []:
            comment_quality, comment_degraded = infer_evidence_quality(comment.get("content"))
            prompt_post["comments"].append(
                {
                    "object_kind": "comment",
                    "comment_id": comment.get("comment_id"),
                    "post_id": comment.get("post_id", post.get("post_id")),
                    "user_id": comment.get("user_id"),
                    "relation_anchor": "unknown",
                    "self_authored": infer_self_authored(
                        object_user_id=comment.get("user_id"),
                        current_agent_id=current_agent_id,
                    ),
                    "summary": summarize_text(
                        comment.get("content_summary") or comment.get("content"), 96
                    ),
                    "evidence_quality": comment_quality,
                    "degraded_evidence": comment_degraded,
                }
            )
        prompt_posts.append(prompt_post)
    return {
        "success": bool(posts_payload.get("success")),
        "posts": prompt_posts,
    }


def build_group_message_samples(
    messages: dict,
    *,
    group_limit: int,
    message_limit: int,
) -> list[str]:
    samples: list[str] = []
    if not isinstance(messages, dict):
        return samples
    for group_id, items in list(messages.items())[:group_limit]:
        for message in (items or [])[:message_limit]:
            if isinstance(message, str):
                summary = summarize_text(message, 80)
            elif isinstance(message, dict):
                summary = summarize_text(message.get("content"), 80)
            else:
                summary = ""
            if summary:
                samples.append(f"group#{group_id}: {summary}")
    return samples


def build_prompt_groups_view(groups: dict) -> dict:
    prompt_groups = {
        "all_groups": groups.get("all_groups", {}),
        "joined_groups": groups.get("joined_groups", []),
        "messages": groups.get("messages", {}),
    }

    all_groups = prompt_groups.get("all_groups", {}) or {}
    if isinstance(all_groups, dict):
        if any(not isinstance(group_name, str) for group_name in all_groups.values()):
            prompt_groups["all_groups"] = all_groups
        else:
            prompt_groups["all_groups"] = {
                str(group_id): summarize_text(group_name, 48)
                for group_id, group_name in list(all_groups.items())
            }

    messages = prompt_groups.get("messages", {}) or {}
    prompt_groups["messages"] = {}
    if isinstance(messages, dict):
        for group_id, items in list(messages.items()):
            if isinstance(items, int) or isinstance(items, str):
                prompt_groups["messages"][group_id] = items
                continue
            rendered_messages = []
            for message in (items or []):
                if isinstance(message, str):
                    rendered_messages.append(summarize_text(message, 96))
                    continue
                if not isinstance(message, dict):
                    continue
                rendered_messages.append(
                    {
                        **message,
                        "content_summary": summarize_text(message.get("content"), 96),
                    }
                )
            prompt_groups["messages"][group_id] = rendered_messages
    return prompt_groups


def build_prompt_visible_groups_snapshot(
    groups_payload: dict[str, Any],
    *,
    current_agent_id: Any = None,
) -> dict[str, Any]:
    all_groups_view = groups_payload.get("all_groups", {}) or {}
    all_groups: list[dict[str, Any]] = []
    if isinstance(all_groups_view, dict) and "group_count" not in all_groups_view:
        for group_id, group_name in list(all_groups_view.items()):
            quality, degraded = infer_evidence_quality(group_name)
            all_groups.append(
                {
                    "object_kind": "group",
                    "group_id": group_id,
                    "relation_anchor": "unknown",
                    "self_authored": False,
                    "summary": summarize_text(group_name, 48),
                    "evidence_quality": quality,
                    "degraded_evidence": degraded,
                }
            )

    joined_groups = groups_payload.get("joined_groups", [])
    if isinstance(joined_groups, dict):
        joined_group_ids = list(joined_groups.get("joined_group_ids", []) or [])
    else:
        joined_group_ids = list(joined_groups or [])

    message_objects: list[dict[str, Any]] = []
    messages_view = groups_payload.get("messages", {}) or {}
    if isinstance(messages_view, dict) and "message_count" not in messages_view:
        for group_id, items in list(messages_view.items()):
            for message in (items or []):
                if isinstance(message, str):
                    quality, degraded = infer_evidence_quality(message)
                    message_objects.append(
                        {
                            "object_kind": "group_message",
                            "group_id": group_id,
                            "message_id": None,
                            "relation_anchor": "unknown",
                            "self_authored": False,
                            "summary": summarize_text(message, 96),
                            "evidence_quality": quality,
                            "degraded_evidence": degraded,
                        }
                    )
                    continue
                if not isinstance(message, dict):
                    continue
                quality, degraded = infer_evidence_quality(message.get("content"))
                message_objects.append(
                    {
                        "object_kind": "group_message",
                        "group_id": group_id,
                        "message_id": message.get("message_id"),
                        "user_id": message.get("user_id") or message.get("sender_id"),
                        "relation_anchor": "unknown",
                        "self_authored": infer_self_authored(
                            object_user_id=message.get("user_id") or message.get("sender_id"),
                            current_agent_id=current_agent_id,
                        ),
                        "summary": summarize_text(
                            message.get("content_summary") or message.get("content"),
                            96,
                        ),
                        "evidence_quality": quality,
                        "degraded_evidence": degraded,
                    }
                )

    degraded_messages = isinstance(messages_view, dict) and "message_count" in messages_view
    degraded_groups = isinstance(all_groups_view, dict) and "group_count" in all_groups_view
    return {
        "success": bool(groups_payload.get("success")),
        "all_groups": all_groups,
        "joined_group_ids": joined_group_ids,
        "messages": message_objects,
        "degraded_groups": degraded_groups,
        "degraded_messages": degraded_messages,
        "message_count": int(
            messages_view.get("message_count", 0) if degraded_messages else len(message_objects)
        ),
    }


def build_prompt_visible_snapshot(
    *,
    posts_payload: dict[str, Any],
    groups_payload: dict[str, Any],
    current_agent_id: Any = None,
) -> dict[str, Any]:
    return {
        "posts": build_prompt_visible_posts_snapshot(
            posts_payload, current_agent_id=current_agent_id
        ),
        "groups": build_prompt_visible_groups_snapshot(
            groups_payload, current_agent_id=current_agent_id
        ),
    }


def extract_semantic_anchors_from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    anchors: list[str] = []
    posts_payload = snapshot.get("posts", {}) or {}
    for post in posts_payload.get("posts", []) or []:
        summary = str(post.get("summary", "") or "").strip()
        if summary:
            anchors.append(f"post#{post.get('post_id')}: {summary}")
        for comment in post.get("comments", []) or []:
            comment_summary = str(comment.get("summary", "") or "").strip()
            if comment_summary:
                anchors.append(f"comment#{comment.get('comment_id')}: {comment_summary}")

    groups_payload = snapshot.get("groups", {}) or {}
    for group in groups_payload.get("all_groups", []) or []:
        if not isinstance(group, dict):
            continue
        group_summary = str(group.get("summary", "") or "").strip()
        if group_summary:
            anchors.append(f"group#{group.get('group_id')}: {group_summary}")
    for message in groups_payload.get("messages", []) or []:
        if not isinstance(message, dict):
            continue
        message_summary = str(message.get("summary", "") or "").strip()
        if message_summary:
            anchors.append(f"group_message#{message.get('message_id')}: {message_summary}")

    return list(dict.fromkeys(anchor for anchor in anchors if anchor))


def extract_topics_from_snapshot(snapshot: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    posts_payload = snapshot.get("posts", {}) or {}
    for post in posts_payload.get("posts", []) or []:
        summary = str(post.get("summary", "") or "").strip()
        if summary:
            topics.append(summary)
    groups_payload = snapshot.get("groups", {}) or {}
    for group in groups_payload.get("all_groups", []) or []:
        if not isinstance(group, dict):
            continue
        summary = str(group.get("summary", "") or "").strip()
        if summary:
            topics.append(summary)
    return list(dict.fromkeys(topic for topic in topics if topic))
