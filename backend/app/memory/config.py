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
class SummaryPresetConfig:
    max_action_items_per_block: int = 4
    compressed_action_block_drop_protected_count: int = 2
    max_action_items_per_recent_turn: int = 6
    max_authored_excerpt_chars: int = 120
    max_target_summary_chars: int = 120
    max_local_context_chars: int = 120
    max_summary_merge_span: int = 3
    max_heartbeat_entity_samples: int = 3
    max_anchor_items_per_block: int = 2
    max_entities_per_heartbeat: int = 3
    max_state_changes_per_turn: int = 4
    max_outcome_digest_chars: int = 160
    compressed_note_title: str = "Compressed short-term memory:"
    recall_note_title: str = "Relevant long-term memory:"
    omit_empty_template_fields: bool = True

    def validate(self) -> None:
        positive_fields = {
            "max_action_items_per_block": self.max_action_items_per_block,
            "compressed_action_block_drop_protected_count": self.compressed_action_block_drop_protected_count,
            "max_action_items_per_recent_turn": self.max_action_items_per_recent_turn,
            "max_authored_excerpt_chars": self.max_authored_excerpt_chars,
            "max_target_summary_chars": self.max_target_summary_chars,
            "max_local_context_chars": self.max_local_context_chars,
            "max_summary_merge_span": self.max_summary_merge_span,
            "max_heartbeat_entity_samples": self.max_heartbeat_entity_samples,
            "max_anchor_items_per_block": self.max_anchor_items_per_block,
            "max_entities_per_heartbeat": self.max_entities_per_heartbeat,
            "max_state_changes_per_turn": self.max_state_changes_per_turn,
            "max_outcome_digest_chars": self.max_outcome_digest_chars,
        }
        for name, value in positive_fields.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
        if not self.compressed_note_title.strip():
            raise ValueError("compressed_note_title must be non-empty.")
        if not self.recall_note_title.strip():
            raise ValueError("recall_note_title must be non-empty.")


@dataclass(slots=True)
class WorkingMemoryBudgetConfig:
    recent_budget_ratio: float = 0.35
    compressed_budget_ratio: float = 0.10
    recall_budget_ratio: float = 0.10
    recent_step_cap: int = 3
    compressed_block_cap: int = 12
    compressed_merge_trigger_ratio: float = 0.90
    generation_reserve_tokens: int = 512

    def validate(self) -> None:
        if not (0 < self.recent_budget_ratio <= 1):
            raise ValueError("recent_budget_ratio must be in (0, 1].")
        if not (0 <= self.compressed_budget_ratio <= 1):
            raise ValueError("compressed_budget_ratio must be in [0, 1].")
        if not (0 <= self.recall_budget_ratio <= 1):
            raise ValueError("recall_budget_ratio must be in [0, 1].")
        if (
            self.recent_budget_ratio
            + self.compressed_budget_ratio
            + self.recall_budget_ratio
            > 1
        ):
            raise ValueError("working memory budget ratios must sum to <= 1.")
        if self.recent_step_cap <= 0:
            raise ValueError("recent_step_cap must be positive.")
        if self.compressed_block_cap <= 0:
            raise ValueError("compressed_block_cap must be positive.")
        if not (0 < self.compressed_merge_trigger_ratio <= 1):
            raise ValueError("compressed_merge_trigger_ratio must be in (0, 1].")
        if self.generation_reserve_tokens < 0:
            raise ValueError("generation_reserve_tokens must be >= 0.")


@dataclass(slots=True)
class ActionV1RuntimeSettings:
    token_counter: TokenCounterLike
    system_message: BaseMessage
    context_token_limit: int
    observation_preset: ObservationPresetConfig = field(
        default_factory=ObservationPresetConfig
    )
    summary_preset: SummaryPresetConfig = field(default_factory=SummaryPresetConfig)
    working_memory_budget: WorkingMemoryBudgetConfig = field(
        default_factory=WorkingMemoryBudgetConfig
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

    @property
    def effective_prompt_budget(self) -> int:
        return max(
            1,
            self.context_token_limit
            - self.working_memory_budget.generation_reserve_tokens,
        )

    def validate(self) -> None:
        if self.context_token_limit <= 0:
            raise ValueError("context_token_limit must be positive.")
        if "{env_prompt}" not in self.observation_wrapper:
            raise ValueError("observation_wrapper must contain '{env_prompt}'.")
        self.observation_preset.validate()
        self.summary_preset.validate()
        self.working_memory_budget.validate()


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


def apply_working_memory_env_overrides(
    preset: WorkingMemoryBudgetConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> WorkingMemoryBudgetConfig:
    env = environ or os.environ
    return WorkingMemoryBudgetConfig(
        recent_budget_ratio=_env_float(
            env,
            "OASIS_V1_RECENT_BUDGET_RATIO",
            preset.recent_budget_ratio,
        ),
        compressed_budget_ratio=_env_float(
            env,
            "OASIS_V1_COMPRESSED_BUDGET_RATIO",
            preset.compressed_budget_ratio,
        ),
        recall_budget_ratio=_env_float(
            env,
            "OASIS_V1_RECALL_BUDGET_RATIO",
            preset.recall_budget_ratio,
        ),
        recent_step_cap=_env_int(
            env,
            "OASIS_V1_RECENT_STEP_CAP",
            preset.recent_step_cap,
        ),
        compressed_block_cap=_env_int(
            env,
            "OASIS_V1_COMPRESSED_BLOCK_CAP",
            preset.compressed_block_cap,
        ),
        compressed_merge_trigger_ratio=_env_float(
            env,
            "OASIS_V1_COMPRESSED_MERGE_TRIGGER_RATIO",
            preset.compressed_merge_trigger_ratio,
        ),
        generation_reserve_tokens=_env_int(
            env,
            "OASIS_V1_GENERATION_RESERVE_TOKENS",
            preset.generation_reserve_tokens,
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
