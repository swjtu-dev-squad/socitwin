from __future__ import annotations

import json
from typing import Any

from oasis.social_agent.agent_environment import SocialEnvironment

from .observation_semantics import build_prompt_groups_view, build_prompt_posts_view


def dumps_compact(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=False,
    )


def render_posts_env(posts_payload: dict[str, Any]) -> str:
    if posts_payload.get("success"):
        posts_env = dumps_compact(
            build_prompt_posts_view(posts_payload.get("posts", []) or [])
        )
        return SocialEnvironment.posts_env_template.substitute(posts=posts_env)
    return "After refreshing, there are no existing posts."


def render_groups_env(groups_payload: dict[str, Any]) -> str:
    if groups_payload.get("success"):
        prompt_groups = build_prompt_groups_view(groups_payload)
        all_groups = dumps_compact(prompt_groups["all_groups"])
        joined_groups = dumps_compact(prompt_groups["joined_groups"])
        messages = dumps_compact(prompt_groups["messages"])
        return SocialEnvironment.groups_env_template.substitute(
            all_groups=all_groups,
            joined_groups=joined_groups,
            messages=messages,
        )
    return "No groups."


def render_observation_prompt(
    posts_payload: dict[str, Any],
    groups_payload: dict[str, Any],
) -> str:
    posts_env = render_posts_env(posts_payload)
    groups_env = render_groups_env(groups_payload)
    return SocialEnvironment.env_template.substitute(
        followers_env="",
        follows_env="",
        posts_env=posts_env,
        groups_env=groups_env,
    )
