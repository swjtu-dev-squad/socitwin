from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from camel.messages import BaseMessage
from camel.models import BaseModelBackend, ModelManager
from camel.types import OpenAIBackendRole
from camel.utils import BaseTokenCounter
from oasis.social_agent.agent_environment import SocialEnvironment


UPSTREAM_OBSERVATION_WRAPPER = (
    "Please perform social media actions after observing the "
    "platform environments. Notice that don't limit your actions "
    "for example to just like the posts. Here is your social media "
    "environment: {env_prompt}"
)


@dataclass(slots=True)
class CompressionConfig:
    assumed_post_count: int
    post_text_cap_chars: int
    comment_text_cap_chars: int
    group_text_cap_chars: int
    head_ratio: float = 0.8


@dataclass(slots=True)
class ModelRuntimeSpec:
    model_platform: str
    model_type: str
    model_config_dict: dict[str, Any] = field(default_factory=dict)
    url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: Optional[float] = None
    max_retries: int = 3
    generation_max_tokens: Optional[int] = None
    declared_context_window: Optional[int] = None
    context_token_limit: Optional[int] = None
    token_counter: Optional[BaseTokenCounter] = None


@dataclass(slots=True)
class ResolvedModelRuntime:
    model: BaseModelBackend | ModelManager
    token_counter: BaseTokenCounter
    context_token_limit: int
    generation_max_tokens: Optional[int]


@dataclass(slots=True)
class ContextRuntimeSettings:
    token_counter: BaseTokenCounter
    system_message: BaseMessage
    context_token_limit: int
    observation_soft_limit: int
    observation_hard_limit: int
    memory_window_size: Optional[int] = None
    observation_wrapper: str = UPSTREAM_OBSERVATION_WRAPPER
    compression: CompressionConfig = field(
        default_factory=lambda: compression_config_for_platform("reddit")
    )

    def validate(self) -> None:
        minimal_prompt = self.observation_wrapper.format(env_prompt="{}")
        system_tokens = self.token_counter.count_tokens_from_messages(
            [
                self.system_message.to_openai_message(
                    OpenAIBackendRole.SYSTEM
                ),
                BaseMessage.make_user_message(
                    role_name="User",
                    content=minimal_prompt,
                ).to_openai_message(OpenAIBackendRole.USER),
            ]
        )
        if system_tokens >= self.observation_hard_limit:
            raise ValueError(
                "Configured context_token_limit is too small for the current "
                "system prompt and observation wrapper."
            )
        bounded_prompt = self._build_minimal_bounded_prompt()
        bounded_tokens = self.token_counter.count_tokens_from_messages(
            [
                self.system_message.to_openai_message(
                    OpenAIBackendRole.SYSTEM
                ),
                BaseMessage.make_user_message(
                    role_name="User",
                    content=self.observation_wrapper.format(
                        env_prompt=bounded_prompt
                    ),
                ).to_openai_message(OpenAIBackendRole.USER),
            ]
        )
        if bounded_tokens > self.observation_hard_limit:
            raise ValueError(
                "Configured context_token_limit is too small even for the "
                "minimal bounded observation shape of the selected preset."
            )

    def _build_minimal_bounded_prompt(self) -> str:
        placeholder = "[truncated from 999999 chars]"
        posts = [
            {
                "post_id": idx,
                "user_id": idx,
                "content": placeholder,
                "created_at": "now",
                "score": 0,
                "num_shares": 0,
                "num_reports": 0,
                "comments": [],
                "comments_omitted_count": 999,
            }
            for idx in range(self.compression.assumed_post_count)
        ]
        posts_env = SocialEnvironment.posts_env_template.substitute(
            posts=json.dumps(
                posts,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=False,
            )
        )
        groups_env = SocialEnvironment.groups_env_template.substitute(
            all_groups=json.dumps(
                {"group_count": 999},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=False,
            ),
            joined_groups=json.dumps(
                {"joined_group_count": 999},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=False,
            ),
            messages=json.dumps(
                {"message_count": 9999},
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=False,
            ),
        )
        return SocialEnvironment.env_template.substitute(
            followers_env="",
            follows_env="",
            posts_env=posts_env,
            groups_env=groups_env,
        )


def compression_config_for_platform(platform: str) -> CompressionConfig:
    normalized = platform.lower()
    if normalized == "twitter":
        return CompressionConfig(
            assumed_post_count=2,
            post_text_cap_chars=640,
            comment_text_cap_chars=256,
            group_text_cap_chars=256,
        )
    return CompressionConfig(
        assumed_post_count=5,
        post_text_cap_chars=384,
        comment_text_cap_chars=192,
        group_text_cap_chars=192,
    )
