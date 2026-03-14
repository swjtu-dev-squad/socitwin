from __future__ import annotations

import copy
import json

from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole
from oasis.social_agent.agent_environment import SocialEnvironment

from .config import ContextRuntimeSettings, build_observation_message_content


COMMENT_ACTIONS = {
    "create_comment",
    "like_comment",
    "unlike_comment",
    "dislike_comment",
    "undo_dislike_comment",
}
GROUP_ACTIONS = {
    "join_group",
    "leave_group",
    "send_to_group",
    "create_group",
}


class ContextSocialEnvironment(SocialEnvironment):
    def __init__(
        self,
        action,
        runtime_settings: ContextRuntimeSettings,
        actionable_tool_names: set[str],
    ):
        super().__init__(action)
        self.runtime_settings = runtime_settings
        self.actionable_tool_names = actionable_tool_names
        self.last_render_stats = {
            "chars_before": 0,
            "chars_after": 0,
            "truncated_field_count": 0,
            "placeholder_field_count": 0,
            "comments_omitted_count": 0,
            "groups_omitted_count": 0,
        }

    async def to_text_prompt(
        self,
        include_posts: bool = True,
        include_followers: bool = True,
        include_follows: bool = True,
    ) -> str:
        del include_followers, include_follows
        posts = await self.action.refresh() if include_posts else {"success": False}
        groups = await self.action.listen_from_group()

        raw_prompt = self._render_prompt(posts, groups)
        self.last_render_stats = {
            "chars_before": len(raw_prompt),
            "chars_after": len(raw_prompt),
            "truncated_field_count": 0,
            "placeholder_field_count": 0,
            "comments_omitted_count": 0,
            "groups_omitted_count": 0,
        }

        if self._prompt_token_count(raw_prompt) <= self.runtime_settings.observation_soft_limit:
            return raw_prompt

        stages = [
            self._apply_truncation,
            self._apply_placeholderization,
            self._apply_non_actionable_summary,
        ]
        working_posts = copy.deepcopy(posts)
        working_groups = copy.deepcopy(groups)
        stats = copy.deepcopy(self.last_render_stats)
        best_prompt = raw_prompt
        best_stats = copy.deepcopy(stats)

        for stage in stages:
            working_posts, working_groups, stats = stage(
                working_posts, working_groups, stats
            )
            prompt = self._render_prompt(working_posts, working_groups)
            stats["chars_after"] = len(prompt)
            prompt_tokens = self._prompt_token_count(prompt)
            if prompt_tokens <= self.runtime_settings.observation_soft_limit:
                self.last_render_stats = stats
                return prompt
            if prompt_tokens <= self.runtime_settings.observation_hard_limit:
                best_prompt = prompt
                best_stats = copy.deepcopy(stats)

        self.last_render_stats = best_stats
        return best_prompt

    def _render_prompt(self, posts: dict, groups: dict) -> str:
        posts_env = self._render_posts_env(posts)
        groups_env = self._render_groups_env(groups)
        return self.env_template.substitute(
            followers_env="",
            follows_env="",
            posts_env=posts_env,
            groups_env=groups_env,
        )

    def _render_posts_env(self, posts: dict) -> str:
        if posts.get("success"):
            posts_env = self._dumps_compact(posts["posts"])
            return self.posts_env_template.substitute(posts=posts_env)
        return "After refreshing, there are no existing posts."

    def _render_groups_env(self, groups: dict) -> str:
        if groups.get("success"):
            all_groups = self._dumps_compact(groups["all_groups"])
            joined_groups = self._dumps_compact(groups["joined_groups"])
            messages = self._dumps_compact(groups["messages"])
            return self.groups_env_template.substitute(
                all_groups=all_groups,
                joined_groups=joined_groups,
                messages=messages,
            )
        return "No groups."

    def _apply_truncation(self, posts: dict, groups: dict, stats: dict):
        if posts.get("success"):
            for post in posts["posts"]:
                content = post.get("content")
                if isinstance(content, str):
                    post["content"] = self._truncate_text(
                        content,
                        self.runtime_settings.compression.post_text_cap_chars,
                        stats,
                    )
                comments = post.get("comments") or []
                for comment in comments:
                    comment_content = comment.get("content")
                    if isinstance(comment_content, str):
                        comment["content"] = self._truncate_text(
                            comment_content,
                            self.runtime_settings.compression.comment_text_cap_chars,
                            stats,
                        )

        if groups.get("success"):
            for messages in groups.get("messages", {}).values():
                for message in messages:
                    content = message.get("content")
                    if isinstance(content, str):
                        message["content"] = self._truncate_text(
                            content,
                            self.runtime_settings.compression.group_text_cap_chars,
                            stats,
                        )

        return posts, groups, stats

    def _apply_placeholderization(self, posts: dict, groups: dict, stats: dict):
        if posts.get("success"):
            for post in posts["posts"]:
                content = post.get("content")
                if isinstance(content, str) and len(content) > self.runtime_settings.compression.post_text_cap_chars:
                    post["content"] = self._placeholder_text(content, stats)
                for comment in post.get("comments") or []:
                    comment_content = comment.get("content")
                    if (
                        isinstance(comment_content, str)
                        and len(comment_content)
                        > self.runtime_settings.compression.comment_text_cap_chars
                    ):
                        comment["content"] = self._placeholder_text(
                            comment_content, stats
                        )

        if groups.get("success"):
            for messages in groups.get("messages", {}).values():
                for message in messages:
                    content = message.get("content")
                    if (
                        isinstance(content, str)
                        and len(content)
                        > self.runtime_settings.compression.group_text_cap_chars
                    ):
                        message["content"] = self._placeholder_text(content, stats)

        return posts, groups, stats

    def _apply_non_actionable_summary(
        self, posts: dict, groups: dict, stats: dict
    ):
        if (
            posts.get("success")
            and not (self.actionable_tool_names & COMMENT_ACTIONS)
        ):
            omitted_comments = 0
            for post in posts["posts"]:
                comments = post.get("comments") or []
                omitted_comments += len(comments)
                post["comments_omitted_count"] = len(comments)
                post["comments"] = []
            stats["comments_omitted_count"] = omitted_comments

        if groups.get("success") and not (self.actionable_tool_names & GROUP_ACTIONS):
            all_groups = groups.get("all_groups", {})
            joined_groups = groups.get("joined_groups", [])
            messages = groups.get("messages", {})
            groups["all_groups"] = {"group_count": len(all_groups)}
            groups["joined_groups"] = {"joined_group_count": len(joined_groups)}
            groups["messages"] = {
                "message_count": sum(len(items) for items in messages.values())
            }
            stats["groups_omitted_count"] = sum(
                len(items) for items in messages.values()
            )

        return posts, groups, stats

    def _prompt_token_count(self, env_prompt: str) -> int:
        full_prompt = build_observation_message_content(
            env_prompt,
            self.runtime_settings.observation_wrapper,
            self.runtime_settings.observation_instruction_suffix,
        )
        user_message = BaseMessage.make_user_message(
            role_name="User", content=full_prompt
        )
        return self.runtime_settings.token_counter.count_tokens_from_messages(
            [
                self.runtime_settings.system_message.to_openai_message(
                    OpenAIBackendRole.SYSTEM
                ),
                user_message.to_openai_message(OpenAIBackendRole.USER),
            ]
        )

    def _truncate_text(self, text: str, cap: int, stats: dict) -> str:
        if len(text) <= cap:
            return text
        stats["truncated_field_count"] += 1
        head_chars = max(1, int(cap * self.runtime_settings.compression.head_ratio))
        tail_chars = max(1, cap - head_chars)
        removed = len(text) - head_chars - tail_chars
        return (
            f"{text[:head_chars]}...[truncated {removed} chars]..."
            f"{text[-tail_chars:]}"
        )

    def _placeholder_text(self, text: str, stats: dict) -> str:
        stats["placeholder_field_count"] += 1
        return f"[truncated from {len(text)} chars]"

    def _dumps_compact(self, value) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=False,
        )
