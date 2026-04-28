from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any

from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from .config import ActionV1RuntimeSettings, ObservationPresetConfig
from .observation_rendering import render_observation_prompt
from .observation_semantics import (
    build_group_message_samples,
    build_prompt_visible_snapshot,
    summarize_text,
)


@dataclass(slots=True)
class ObservationArtifact:
    observation_prompt: str
    prompt_visible_snapshot: dict[str, Any]
    render_stats: dict[str, Any]
    source_snapshot_kind: str
    visible_payload: dict[str, Any]


def build_minimal_bounded_visible_payload(
    preset: ObservationPresetConfig,
) -> dict[str, dict[str, Any]]:
    placeholder = "[placeholder observation content]"
    return {
        "posts": {
            "success": True,
            "posts": [
                {
                    "post_id": 1,
                    "user_id": 1,
                    "content": placeholder,
                    "created_at": "now",
                    "score": 0,
                    "num_shares": 0,
                    "num_reports": 0,
                    "comments": [],
                    "comments_omitted_count": 1,
                }
            ],
        },
        "groups": {
            "success": True,
            "all_groups": {
                "group_count": 1,
                "group_samples": ["group sample"][: preset.physical_fallback_group_sample_count],
            },
            "joined_groups": {
                "joined_group_count": 1,
                "joined_group_ids": [1][: preset.physical_fallback_joined_group_id_sample_count],
            },
            "messages": {
                "message_count": 1,
                "message_samples": ["group#1: placeholder observation content"][
                    : preset.physical_fallback_message_sample_count
                ],
            },
        },
    }


class ObservationShaper:
    def __init__(self, runtime_settings: ActionV1RuntimeSettings) -> None:
        self.runtime_settings = runtime_settings

    def shape(
        self,
        *,
        posts_payload: dict[str, Any],
        groups_payload: dict[str, Any],
        current_agent_id: Any = None,
    ) -> ObservationArtifact:
        raw_posts = copy.deepcopy(posts_payload or {"success": False})
        raw_groups = copy.deepcopy(groups_payload or {"success": False})
        raw_payload = {"posts": raw_posts, "groups": raw_groups}
        raw_counts = self._raw_family_counts(raw_posts, raw_groups)
        visible_payload, stats = self._apply_raw_guards(
            raw_posts=raw_posts,
            raw_groups=raw_groups,
            raw_counts=raw_counts,
        )

        prompt = self._render_prompt(visible_payload["posts"], visible_payload["groups"])
        tokens = self._prompt_token_count(prompt)
        if tokens <= self.runtime_settings.observation_target_budget:
            stage = "raw_fit" if raw_payload == visible_payload else "guarded_raw_fit"
            return self._build_artifact(
                visible_payload=visible_payload,
                current_agent_id=current_agent_id,
                raw_counts=raw_counts,
                stats=stats,
                stage=stage,
            )

        hard_capped = self._apply_long_text_cap(visible_payload=visible_payload, stats=stats)
        hard_capped_prompt = self._render_prompt(hard_capped["posts"], hard_capped["groups"])
        hard_capped_tokens = self._prompt_token_count(hard_capped_prompt)
        if hard_capped_tokens <= self.runtime_settings.observation_hard_budget:
            return self._build_artifact(
                visible_payload=hard_capped,
                current_agent_id=current_agent_id,
                raw_counts=raw_counts,
                stats=stats,
                stage="long_text_capped",
            )

        interaction_payload, interaction_stats, interaction_tokens = self._apply_interaction_shrink(
            visible_payload=hard_capped,
            stats=stats,
        )
        if interaction_tokens <= self.runtime_settings.observation_hard_budget:
            return self._build_artifact(
                visible_payload=interaction_payload,
                current_agent_id=current_agent_id,
                raw_counts=raw_counts,
                stats=interaction_stats,
                stage="interaction_reduced",
            )

        physical = self._apply_physical_fallback(interaction_payload)
        return self._build_artifact(
            visible_payload=physical,
            current_agent_id=current_agent_id,
            raw_counts=raw_counts,
            stats=interaction_stats,
            stage="physical_fallback",
        )

    def _init_render_stats(self, raw_counts: dict[str, int]) -> dict[str, Any]:
        return {
            "selected_post_count": 0,
            "selected_comment_count": 0,
            "selected_group_count": 0,
            "selected_group_message_count": 0,
            "omitted_post_count": raw_counts["post_count"],
            "omitted_comment_count": raw_counts["comment_count"],
            "omitted_group_count": raw_counts["group_count"],
            "omitted_group_message_count": raw_counts["group_message_count"],
            "comments_omitted_count": raw_counts["comment_count"],
            "groups_omitted_count": raw_counts["group_count"],
            "group_messages_omitted_count": raw_counts["group_message_count"],
            "truncated_field_count": 0,
            "raw_guard_applied": False,
            "raw_guard_group_trimmed": 0,
            "raw_guard_comment_trimmed": 0,
            "raw_guard_message_trimmed": 0,
            "interaction_shrink_rounds": 0,
            "final_shaping_stage": "raw_fit",
        }

    def _build_artifact(
        self,
        *,
        visible_payload: dict[str, Any],
        current_agent_id: Any,
        raw_counts: dict[str, int],
        stats: dict[str, Any],
        stage: str,
    ) -> ObservationArtifact:
        posts_payload = visible_payload["posts"]
        groups_payload = visible_payload["groups"]
        prompt_visible_snapshot = build_prompt_visible_snapshot(
            posts_payload=posts_payload,
            groups_payload=groups_payload,
            current_agent_id=current_agent_id,
        )
        observation_prompt = self._render_prompt(posts_payload, groups_payload)
        selected_counts = self._selected_family_counts(posts_payload, groups_payload)
        final_stats = dict(stats)
        final_stats.update(
            {
                "selected_post_count": selected_counts["post_count"],
                "selected_comment_count": selected_counts["comment_count"],
                "selected_group_count": selected_counts["group_count"],
                "selected_group_message_count": selected_counts["group_message_count"],
                "omitted_post_count": max(0, raw_counts["post_count"] - selected_counts["post_count"]),
                "omitted_comment_count": max(0, raw_counts["comment_count"] - selected_counts["comment_count"]),
                "omitted_group_count": max(0, raw_counts["group_count"] - selected_counts["group_count"]),
                "omitted_group_message_count": max(
                    0, raw_counts["group_message_count"] - selected_counts["group_message_count"]
                ),
                "comments_omitted_count": max(0, raw_counts["comment_count"] - selected_counts["comment_count"]),
                "groups_omitted_count": max(0, raw_counts["group_count"] - selected_counts["group_count"]),
                "group_messages_omitted_count": max(
                    0, raw_counts["group_message_count"] - selected_counts["group_message_count"]
                ),
                "final_shaping_stage": stage,
                "observation_prompt_tokens": self._prompt_token_count(observation_prompt),
            }
        )
        return ObservationArtifact(
            observation_prompt=observation_prompt,
            prompt_visible_snapshot=prompt_visible_snapshot,
            render_stats=final_stats,
            source_snapshot_kind="prompt_visible_snapshot",
            visible_payload={"posts": copy.deepcopy(posts_payload), "groups": copy.deepcopy(groups_payload)},
        )

    def _apply_raw_guards(
        self,
        *,
        raw_posts: dict[str, Any],
        raw_groups: dict[str, Any],
        raw_counts: dict[str, int],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        preset = self.runtime_settings.observation_preset
        stats = self._init_render_stats(raw_counts)
        visible_posts = copy.deepcopy(raw_posts)
        visible_groups = copy.deepcopy(raw_groups)
        guard_applied = False

        if visible_posts.get("success"):
            posts = list(visible_posts.get("posts", []) or [])
            kept_comment_counts = _allocate_total_by_parent(
                [len(post.get("comments", []) or []) for post in posts],
                preset.comments_total_guard,
            )
            trimmed_comments = 0
            for post, keep_count in zip(posts, kept_comment_counts, strict=False):
                comments = list(post.get("comments", []) or [])
                trimmed_comments += max(0, len(comments) - keep_count)
                post["comments"] = comments[:keep_count]
                post["comments_omitted_count"] = max(0, len(comments) - keep_count)
            visible_posts["posts"] = posts
            if trimmed_comments > 0:
                guard_applied = True
                stats["raw_guard_comment_trimmed"] = trimmed_comments

        if visible_groups.get("success"):
            all_groups = visible_groups.get("all_groups", {}) or {}
            selected_group_items = list(all_groups.items())[: preset.groups_count_guard]
            selected_group_ids = [group_id for group_id, _ in selected_group_items]
            trimmed_groups = max(0, len(all_groups) - len(selected_group_items))
            if trimmed_groups > 0:
                guard_applied = True
                stats["raw_guard_group_trimmed"] = trimmed_groups
            visible_groups["all_groups"] = dict(selected_group_items)
            joined_groups = list(visible_groups.get("joined_groups", []) or [])
            visible_groups["joined_groups"] = [
                group_id for group_id in joined_groups if group_id in set(selected_group_ids)
            ]
            raw_messages = visible_groups.get("messages", {}) or {}
            filtered_messages = {
                group_id: list(raw_messages.get(group_id, []) or [])
                for group_id in selected_group_ids
                if group_id in raw_messages
            }
            kept_message_counts = _allocate_total_by_parent(
                [len(filtered_messages.get(group_id, []) or []) for group_id in selected_group_ids],
                preset.messages_total_guard,
            )
            trimmed_messages = 0
            visible_groups["messages"] = {}
            for group_id, keep_count in zip(selected_group_ids, kept_message_counts, strict=False):
                messages = list(filtered_messages.get(group_id, []) or [])
                trimmed_messages += max(0, len(messages) - keep_count)
                visible_groups["messages"][group_id] = messages[:keep_count]
            if trimmed_messages > 0:
                guard_applied = True
                stats["raw_guard_message_trimmed"] = trimmed_messages

        stats["raw_guard_applied"] = guard_applied
        return {"posts": visible_posts, "groups": visible_groups}, stats

    def _apply_long_text_cap(
        self,
        *,
        visible_payload: dict[str, Any],
        stats: dict[str, Any],
    ) -> dict[str, Any]:
        preset = self.runtime_settings.observation_preset
        capped = copy.deepcopy(visible_payload)
        for post in capped["posts"].get("posts", []) or []:
            post["content"] = self._compact_text(post.get("content"), preset.post_text_cap_chars, stats)
            for comment in post.get("comments", []) or []:
                comment["content"] = self._compact_text(
                    comment.get("content"), preset.comment_text_cap_chars, stats
                )
        for group_id, messages in (capped["groups"].get("messages", {}) or {}).items():
            capped["groups"]["messages"][group_id] = [
                self._compact_message(message, preset.message_text_cap_chars, stats)
                for message in (messages or [])
            ]
        return capped

    def _apply_interaction_shrink(
        self,
        *,
        visible_payload: dict[str, Any],
        stats: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
        hard_budget = self.runtime_settings.observation_hard_budget
        next_stats = dict(stats)
        current = copy.deepcopy(visible_payload)
        current_tokens = self._payload_token_count(current)
        if current_tokens <= hard_budget:
            return current, next_stats, current_tokens

        comment_total = _count_visible_comments(current["posts"])
        message_total = _count_visible_messages(current["groups"])
        overflow_ratio = current_tokens / max(hard_budget, 1)
        if overflow_ratio > 1.15 and (comment_total > 0 or message_total > 0):
            scale = hard_budget / max(current_tokens, 1)
            safe_scale = min(0.9, max(0.0, scale * 0.95))
            shrunk_comment_total = 0 if comment_total <= 0 else max(0, math.floor(comment_total * safe_scale))
            shrunk_message_total = 0 if message_total <= 0 else max(0, math.floor(message_total * safe_scale))
            current = self._apply_interaction_totals(
                visible_payload=current,
                comment_total=shrunk_comment_total,
                message_total=shrunk_message_total,
            )
            current_tokens = self._payload_token_count(current)
            next_stats["interaction_shrink_rounds"] += 1

        for _ in range(6):
            if current_tokens <= hard_budget:
                break
            current_comment_total = _count_visible_comments(current["posts"])
            current_message_total = _count_visible_messages(current["groups"])
            candidates: list[tuple[int, int, dict[str, Any], int]] = []
            comment_step = max(1, math.ceil(current_comment_total * 0.05)) if current_comment_total > 0 else 0
            message_step = max(1, math.ceil(current_message_total * 0.05)) if current_message_total > 0 else 0
            for next_comment_total, next_message_total in {
                (max(0, current_comment_total - comment_step), current_message_total),
                (current_comment_total, max(0, current_message_total - message_step)),
                (
                    max(0, current_comment_total - comment_step),
                    max(0, current_message_total - message_step),
                ),
            }:
                if next_comment_total == current_comment_total and next_message_total == current_message_total:
                    continue
                candidate = self._apply_interaction_totals(
                    visible_payload=current,
                    comment_total=next_comment_total,
                    message_total=next_message_total,
                )
                candidate_tokens = self._payload_token_count(candidate)
                candidates.append(
                    (next_comment_total + next_message_total, candidate_tokens, candidate, next_comment_total)
                )
            if not candidates:
                break
            fitting = [item for item in candidates if item[1] <= hard_budget]
            if fitting:
                fitting.sort(key=lambda item: (-item[0], item[1], -item[3]))
                _, current_tokens, current, _ = fitting[0]
                next_stats["interaction_shrink_rounds"] += 1
                break
            candidates.sort(key=lambda item: (item[1], -item[0], -item[3]))
            _, current_tokens, current, _ = candidates[0]
            next_stats["interaction_shrink_rounds"] += 1
        return current, next_stats, current_tokens

    def _apply_interaction_totals(
        self,
        *,
        visible_payload: dict[str, Any],
        comment_total: int,
        message_total: int,
    ) -> dict[str, Any]:
        reduced = copy.deepcopy(visible_payload)
        posts = reduced["posts"].get("posts", []) or []
        comment_allocations = _allocate_total_by_parent(
            [len(post.get("comments", []) or []) for post in posts],
            comment_total,
        )
        for post, keep_count in zip(posts, comment_allocations, strict=False):
            comments = list(post.get("comments", []) or [])
            post["comments"] = comments[:keep_count]
            post["comments_omitted_count"] = max(
                int(post.get("comments_omitted_count", 0) or 0),
                len(comments) - keep_count,
            )

        groups_messages = reduced["groups"].get("messages", {}) or {}
        group_ids = list(groups_messages.keys())
        message_allocations = _allocate_total_by_parent(
            [len(groups_messages.get(group_id, []) or []) for group_id in group_ids],
            message_total,
        )
        for group_id, keep_count in zip(group_ids, message_allocations, strict=False):
            messages = list(groups_messages.get(group_id, []) or [])
            reduced["groups"]["messages"][group_id] = messages[:keep_count]
        return reduced

    def _apply_physical_fallback(self, visible_payload: dict[str, Any]) -> dict[str, Any]:
        preset = self.runtime_settings.observation_preset
        fallback = copy.deepcopy(visible_payload)
        posts = list(fallback["posts"].get("posts", []) or [])[
            : preset.physical_fallback_post_sample_count
        ]
        compact_posts: list[dict[str, Any]] = []
        for post in posts:
            compact_post = dict(post)
            compact_post["comments_omitted_count"] = int(compact_post.get("comments_omitted_count", 0) or 0) + len(
                compact_post.get("comments", []) or []
            )
            compact_post["comments"] = []
            compact_posts.append(compact_post)
        fallback["posts"]["posts"] = compact_posts

        all_groups = fallback["groups"].get("all_groups", {}) or {}
        joined_groups = list(fallback["groups"].get("joined_groups", []) or [])
        messages = fallback["groups"].get("messages", {}) or {}
        fallback["groups"]["all_groups"] = {
            "group_count": len(all_groups),
            "group_samples": [
                summarize_text(name, 48)
                for _, name in list(all_groups.items())[: preset.physical_fallback_group_sample_count]
                if isinstance(name, str) and name.strip()
            ],
        }
        fallback["groups"]["joined_groups"] = {
            "joined_group_count": len(joined_groups),
            "joined_group_ids": joined_groups[: preset.physical_fallback_joined_group_id_sample_count],
        }
        fallback["groups"]["messages"] = {
            "message_count": sum(len(items or []) for items in messages.values()),
            "message_samples": build_group_message_samples(
                messages,
                group_limit=preset.physical_fallback_message_group_limit,
                message_limit=preset.physical_fallback_message_sample_count,
            ),
        }
        return fallback

    def _compact_message(self, message: Any, cap: int, stats: dict[str, Any]) -> Any:
        if not isinstance(message, dict):
            return message
        compacted = dict(message)
        compacted["content"] = self._compact_text(compacted.get("content"), cap, stats)
        return compacted

    def _compact_text(self, value: Any, cap: int, stats: dict[str, Any]) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if len(text) <= cap:
            return value
        summary = summarize_text(text, cap)
        stats["truncated_field_count"] += 1
        return f"{summary} ...[compacted from {len(text)} chars]"

    def _raw_family_counts(self, raw_posts: dict[str, Any], raw_groups: dict[str, Any]) -> dict[str, int]:
        post_list = list(raw_posts.get("posts", []) or []) if raw_posts.get("success") else []
        all_groups = raw_groups.get("all_groups", {}) or {} if raw_groups.get("success") else {}
        messages = raw_groups.get("messages", {}) or {} if raw_groups.get("success") else {}
        return {
            "post_count": len(post_list),
            "comment_count": sum(len(post.get("comments", []) or []) for post in post_list),
            "group_count": len(all_groups) if isinstance(all_groups, dict) else 0,
            "group_message_count": sum(len(items or []) for items in messages.values())
            if isinstance(messages, dict)
            else 0,
        }

    def _selected_family_counts(self, posts_payload: dict[str, Any], groups_payload: dict[str, Any]) -> dict[str, int]:
        posts = list(posts_payload.get("posts", []) or []) if posts_payload.get("success") else []
        groups_view = groups_payload.get("all_groups", {}) or {}
        messages_view = groups_payload.get("messages", {}) or {}
        if isinstance(groups_view, dict) and "group_count" in groups_view:
            selected_groups = len(groups_view.get("group_samples", []) or [])
        elif isinstance(groups_view, dict):
            selected_groups = len(groups_view)
        else:
            selected_groups = 0
        if isinstance(messages_view, dict) and "message_count" in messages_view:
            selected_messages = len(messages_view.get("message_samples", []) or [])
        elif isinstance(messages_view, dict):
            selected_messages = sum(len(items or []) for items in messages_view.values())
        else:
            selected_messages = 0
        return {
            "post_count": len(posts),
            "comment_count": sum(len(post.get("comments", []) or []) for post in posts),
            "group_count": selected_groups,
            "group_message_count": selected_messages,
        }

    def _render_prompt(self, posts_payload: dict[str, Any], groups_payload: dict[str, Any]) -> str:
        return render_observation_prompt(posts_payload, groups_payload)

    def _payload_token_count(self, visible_payload: dict[str, Any]) -> int:
        return self._prompt_token_count(
            self._render_prompt(visible_payload["posts"], visible_payload["groups"])
        )

    def _prompt_token_count(self, env_prompt: str) -> int:
        full_prompt = self.runtime_settings.observation_wrapper.format(env_prompt=env_prompt)
        user_message = BaseMessage.make_user_message(role_name="User", content=full_prompt)
        return self.runtime_settings.token_counter.count_tokens_from_messages(
            [
                self.runtime_settings.system_message.to_openai_message(OpenAIBackendRole.SYSTEM),
                user_message.to_openai_message(OpenAIBackendRole.USER),
            ]
        )


def _count_visible_comments(posts_payload: dict[str, Any]) -> int:
    posts = list(posts_payload.get("posts", []) or []) if posts_payload.get("success") else []
    return sum(len(post.get("comments", []) or []) for post in posts)


def _count_visible_messages(groups_payload: dict[str, Any]) -> int:
    messages = groups_payload.get("messages", {}) or {}
    if not isinstance(messages, dict) or "message_count" in messages:
        return 0
    return sum(len(items or []) for items in messages.values())


def _allocate_total_by_parent(parent_lengths: list[int], total_cap: int) -> list[int]:
    allocations = [0 for _ in parent_lengths]
    remaining = max(0, total_cap)
    if remaining <= 0:
        return allocations

    for index, parent_length in enumerate(parent_lengths):
        if remaining <= 0:
            break
        if parent_length <= 0:
            continue
        allocations[index] = 1
        remaining -= 1

    if remaining <= 0:
        return allocations

    for index, parent_length in enumerate(parent_lengths):
        parent_cap = max(0, parent_length - allocations[index])
        if parent_cap <= 0:
            continue
        extra = min(parent_cap, remaining)
        allocations[index] += extra
        remaining -= extra
        if remaining <= 0:
            break
    return allocations
