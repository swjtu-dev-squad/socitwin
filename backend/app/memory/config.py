from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Mapping, Protocol

from camel.messages import BaseMessage


UPSTREAM_OBSERVATION_WRAPPER = (
    "Please perform social media actions after observing the "
    "platform environments. Notice that don't limit your actions "
    "for example to just like the posts. Here is your social media "
    "environment: {env_prompt}"
)


class MemoryMode(str, Enum):
    """Supported memory runtimes in the new repository."""

    UPSTREAM = "upstream"
    ACTION_V1 = "action_v1"


@dataclass(slots=True)
class MemoryRuntimeConfig:
    """Minimal Phase-1 memory runtime configuration."""

    mode: MemoryMode = MemoryMode.UPSTREAM


class TokenCounterLike(Protocol):
    def count_tokens_from_messages(self, messages) -> int:
        ...


@dataclass(slots=True)
class ObservationPresetConfig:
    groups_count_guard: int = 64
    comments_total_guard: int = 512
    messages_total_guard: int = 512
    post_text_cap_chars: int = 1200
    comment_text_cap_chars: int = 900
    message_text_cap_chars: int = 240
    physical_fallback_joined_group_id_sample_count: int = 12
    physical_fallback_message_group_limit: int = 4
    observation_target_ratio: float = 0.50
    observation_hard_ratio: float = 0.60
    physical_fallback_post_sample_count: int = 2
    physical_fallback_group_sample_count: int = 2
    physical_fallback_message_sample_count: int = 2

    def validate(self) -> None:
        if self.groups_count_guard <= 0:
            raise ValueError("groups_count_guard must be positive.")
        if self.comments_total_guard <= 0:
            raise ValueError("comments_total_guard must be positive.")
        if self.messages_total_guard <= 0:
            raise ValueError("messages_total_guard must be positive.")
        if self.post_text_cap_chars <= 0:
            raise ValueError("post_text_cap_chars must be positive.")
        if self.comment_text_cap_chars <= 0:
            raise ValueError("comment_text_cap_chars must be positive.")
        if self.message_text_cap_chars <= 0:
            raise ValueError("message_text_cap_chars must be positive.")
        if not (0 < self.observation_target_ratio <= self.observation_hard_ratio <= 1):
            raise ValueError("observation ratios must satisfy 0 < target <= hard <= 1.")


@dataclass(slots=True)
class ActionV1RuntimeSettings:
    token_counter: TokenCounterLike
    system_message: BaseMessage
    context_token_limit: int
    observation_preset: ObservationPresetConfig = field(
        default_factory=ObservationPresetConfig
    )
    observation_wrapper: str = UPSTREAM_OBSERVATION_WRAPPER

    @property
    def observation_target_budget(self) -> int:
        return max(
            1,
            int(self.context_token_limit * self.observation_preset.observation_target_ratio),
        )

    @property
    def observation_hard_budget(self) -> int:
        return max(
            self.observation_target_budget,
            int(self.context_token_limit * self.observation_preset.observation_hard_ratio),
        )

    def validate(self) -> None:
        if self.context_token_limit <= 0:
            raise ValueError("context_token_limit must be positive.")
        if "{env_prompt}" not in self.observation_wrapper:
            raise ValueError("observation_wrapper must contain '{env_prompt}'.")
        self.observation_preset.validate()


def normalize_memory_mode(value: MemoryMode | str | None) -> MemoryMode:
    """Normalize explicit mode strings from API/config/env surfaces."""

    if isinstance(value, MemoryMode):
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return MemoryMode.UPSTREAM
    try:
        return MemoryMode(normalized)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in MemoryMode)
        raise ValueError(
            f"Unsupported memory mode '{value}'. Expected one of: {allowed}."
        ) from exc


def resolve_memory_runtime_config(
    *,
    explicit_mode: MemoryMode | str | None = None,
    settings_mode: str | None = None,
) -> MemoryRuntimeConfig:
    """Resolve the Phase-1 runtime mode with explicit config taking priority."""

    if explicit_mode not in (None, ""):
        return MemoryRuntimeConfig(mode=normalize_memory_mode(explicit_mode))
    return MemoryRuntimeConfig(mode=normalize_memory_mode(settings_mode))


def apply_observation_env_overrides(
    preset: ObservationPresetConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> ObservationPresetConfig:
    env = environ or os.environ
    return ObservationPresetConfig(
        groups_count_guard=_env_int(
            env,
            "OASIS_V1_OBS_GROUPS_COUNT_GUARD",
            preset.groups_count_guard,
        ),
        comments_total_guard=_env_int(
            env,
            "OASIS_V1_OBS_COMMENTS_TOTAL_GUARD",
            preset.comments_total_guard,
        ),
        messages_total_guard=_env_int(
            env,
            "OASIS_V1_OBS_MESSAGES_TOTAL_GUARD",
            preset.messages_total_guard,
        ),
        post_text_cap_chars=_env_int(
            env,
            "OASIS_V1_OBS_POST_TEXT_CAP_CHARS",
            preset.post_text_cap_chars,
        ),
        comment_text_cap_chars=_env_int(
            env,
            "OASIS_V1_OBS_COMMENT_TEXT_CAP_CHARS",
            preset.comment_text_cap_chars,
        ),
        message_text_cap_chars=_env_int(
            env,
            "OASIS_V1_OBS_MESSAGE_TEXT_CAP_CHARS",
            preset.message_text_cap_chars,
        ),
        physical_fallback_joined_group_id_sample_count=_env_int(
            env,
            "OASIS_V1_OBS_PHYSICAL_FALLBACK_JOINED_GROUP_ID_SAMPLE_COUNT",
            preset.physical_fallback_joined_group_id_sample_count,
        ),
        physical_fallback_message_group_limit=_env_int(
            env,
            "OASIS_V1_OBS_PHYSICAL_FALLBACK_MESSAGE_GROUP_LIMIT",
            preset.physical_fallback_message_group_limit,
        ),
        observation_target_ratio=_env_float(
            env,
            "OASIS_V1_OBS_TARGET_RATIO",
            preset.observation_target_ratio,
        ),
        observation_hard_ratio=_env_float(
            env,
            "OASIS_V1_OBS_HARD_RATIO",
            preset.observation_hard_ratio,
        ),
        physical_fallback_post_sample_count=_env_int(
            env,
            "OASIS_V1_OBS_PHYSICAL_FALLBACK_POST_SAMPLE_COUNT",
            preset.physical_fallback_post_sample_count,
        ),
        physical_fallback_group_sample_count=_env_int(
            env,
            "OASIS_V1_OBS_PHYSICAL_FALLBACK_GROUP_SAMPLE_COUNT",
            preset.physical_fallback_group_sample_count,
        ),
        physical_fallback_message_sample_count=_env_int(
            env,
            "OASIS_V1_OBS_PHYSICAL_FALLBACK_MESSAGE_SAMPLE_COUNT",
            preset.physical_fallback_message_sample_count,
        ),
    )


def _env_int(environ: Mapping[str, str], key: str, default: int) -> int:
    value = environ.get(key)
    if value in (None, ""):
        return default
    return int(value)


def _env_float(environ: Mapping[str, str], key: str, default: float) -> float:
    value = environ.get(key)
    if value in (None, ""):
        return default
    return float(value)
