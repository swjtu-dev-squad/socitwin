from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, TypedDict

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


MatcherTuple = tuple[Any, ...]
MatcherCategoryMap = dict[str, MatcherTuple]
StructuredMatcherSection = dict[str, MatcherCategoryMap]


class ProviderMatcherFamily(TypedDict):
    structured: StructuredMatcherSection
    normalized_patterns: MatcherCategoryMap
    raw_patterns: MatcherCategoryMap


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
            "compressed_action_block_drop_protected_count": (
                self.compressed_action_block_drop_protected_count
            ),
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
class RecallPresetConfig:
    retrieval_limit: int = 3
    cooldown_steps: int = 2
    min_trigger_entity_count: int = 0
    allow_topic_trigger: bool = True
    allow_anchor_trigger: bool = True
    allow_recent_action_trigger: bool = True
    allow_self_authored_trigger: bool = True
    deny_repeated_query_within_steps: int = 2
    max_reason_trace_chars: int = 120

    def validate(self) -> None:
        if self.retrieval_limit <= 0:
            raise ValueError("retrieval_limit must be positive.")
        if self.cooldown_steps < 0:
            raise ValueError("cooldown_steps must be >= 0.")
        if self.min_trigger_entity_count < 0:
            raise ValueError("min_trigger_entity_count must be >= 0.")
        if self.deny_repeated_query_within_steps < 0:
            raise ValueError("deny_repeated_query_within_steps must be >= 0.")
        if self.max_reason_trace_chars <= 0:
            raise ValueError("max_reason_trace_chars must be positive.")


@dataclass(slots=True)
class LongtermSidecarConfig:
    enabled: bool = False
    store: Any | None = None
    retrieval_limit: int = 3

    def validate(self) -> None:
        if self.retrieval_limit <= 0:
            raise ValueError("longterm_sidecar.retrieval_limit must be positive.")


@dataclass(slots=True)
class ProviderRuntimePresetConfig:
    provider_error_matchers: dict[str, ProviderMatcherFamily] = field(
        default_factory=lambda: {
            "openai": {
                "structured": {
                    "status_codes": {"context_overflow": (400, 413)},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": (
                        "maximum context length",
                        "context length exceeded",
                        "prompt is too long",
                        "request too large",
                    ),
                },
                "raw_patterns": {},
            },
            "openrouter": {
                "structured": {
                    "status_codes": {"context_overflow": (400, 413)},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": (
                        "maximum context length",
                        "context length exceeded",
                        "prompt is too long",
                        "request too large",
                    ),
                },
                "raw_patterns": {},
            },
            "deepseek": {
                "structured": {
                    "status_codes": {"context_overflow": (400, 413)},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": (
                        "maximum context length",
                        "context length exceeded",
                        "prompt is too long",
                        "request too large",
                    ),
                },
                "raw_patterns": {},
            },
            "vllm": {
                "structured": {
                    "status_codes": {"context_overflow": (400, 413)},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": (
                        "maximum context length",
                        "context length exceeded",
                        "token limit exceeded",
                        "request too large",
                    ),
                },
                "raw_patterns": {},
            },
            "ollama": {
                "structured": {
                    "status_codes": {"context_overflow": (400, 413)},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": (
                        "input length exceeds",
                        "context length exceeded",
                        "token limit exceeded",
                        "prompt too long",
                    ),
                },
                "raw_patterns": {},
            },
            "*": {
                "structured": {
                    "status_codes": {},
                    "error_codes": {},
                    "exception_types": {},
                },
                "normalized_patterns": {
                    "context_overflow": (
                        "maximum context",
                        "context length",
                        "prompt too long",
                        "request too large",
                        "token limit exceeded",
                        "max context",
                    ),
                },
                "raw_patterns": {},
            },
        }
    )
    provider_overflow_penalty_native_tiers: tuple[tuple[int, float], ...] = (
        (256, 0.03),
        (512, 0.06),
    )
    provider_overflow_penalty_heuristic_tiers: tuple[tuple[int, float], ...] = (
        (512, 0.06),
        (1024, 0.12),
    )
    counter_uncertainty_reserve_policy: str = "heuristic_10pct_min256"
    max_budget_retries: int = 4

    def validate(self) -> None:
        if "*" not in self.provider_error_matchers:
            raise ValueError("provider_error_matchers must include '*' fallback.")
        if not self.counter_uncertainty_reserve_policy.strip():
            raise ValueError("counter_uncertainty_reserve_policy must be non-empty.")
        for name, tiers in {
            "provider_overflow_penalty_native_tiers": self.provider_overflow_penalty_native_tiers,
            "provider_overflow_penalty_heuristic_tiers": (
                self.provider_overflow_penalty_heuristic_tiers
            ),
        }.items():
            if not tiers:
                raise ValueError(f"{name} must contain at least one tier.")
            for minimum_tokens, ratio in tiers:
                if minimum_tokens <= 0:
                    raise ValueError(f"{name} minimum tokens must be positive.")
                if ratio <= 0:
                    raise ValueError(f"{name} ratios must be positive.")
        if self.max_budget_retries <= 0:
            raise ValueError("max_budget_retries must be positive.")


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
    recall_preset: RecallPresetConfig = field(default_factory=RecallPresetConfig)
    longterm_sidecar: LongtermSidecarConfig = field(default_factory=LongtermSidecarConfig)
    provider_runtime_preset: ProviderRuntimePresetConfig = field(
        default_factory=ProviderRuntimePresetConfig
    )
    memory_window_size: int | None = None
    prompt_assembly_enabled: bool = True
    token_counter_mode: str = "heuristic_fallback"
    context_window_source: str = "settings_context_limit"
    model_backend_family: str = "unknown"
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
        self.recall_preset.validate()
        self.longterm_sidecar.validate()
        self.provider_runtime_preset.validate()


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


def apply_recall_env_overrides(
    preset: RecallPresetConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> RecallPresetConfig:
    env = environ or os.environ
    return RecallPresetConfig(
        retrieval_limit=_env_int(
            env,
            "OASIS_V1_RECALL_LIMIT",
            preset.retrieval_limit,
        ),
        cooldown_steps=_env_int(
            env,
            "OASIS_V1_RECALL_COOLDOWN_STEPS",
            preset.cooldown_steps,
        ),
        min_trigger_entity_count=_env_int(
            env,
            "OASIS_V1_RECALL_MIN_TRIGGER_ENTITY_COUNT",
            preset.min_trigger_entity_count,
        ),
        allow_topic_trigger=_env_bool(
            env,
            "OASIS_V1_RECALL_ALLOW_TOPIC_TRIGGER",
            preset.allow_topic_trigger,
        ),
        allow_anchor_trigger=_env_bool(
            env,
            "OASIS_V1_RECALL_ALLOW_ANCHOR_TRIGGER",
            preset.allow_anchor_trigger,
        ),
        allow_recent_action_trigger=_env_bool(
            env,
            "OASIS_V1_RECALL_ALLOW_RECENT_ACTION_TRIGGER",
            preset.allow_recent_action_trigger,
        ),
        allow_self_authored_trigger=_env_bool(
            env,
            "OASIS_V1_RECALL_ALLOW_SELF_AUTHORED_TRIGGER",
            preset.allow_self_authored_trigger,
        ),
        deny_repeated_query_within_steps=_env_int(
            env,
            "OASIS_V1_RECALL_DENY_REPEATED_QUERY_WITHIN_STEPS",
            preset.deny_repeated_query_within_steps,
        ),
        max_reason_trace_chars=_env_int(
            env,
            "OASIS_V1_RECALL_MAX_REASON_TRACE_CHARS",
            preset.max_reason_trace_chars,
        ),
    )


def apply_summary_env_overrides(
    preset: SummaryPresetConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> SummaryPresetConfig:
    env = environ or os.environ
    return SummaryPresetConfig(
        max_action_items_per_block=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_ACTION_ITEMS_PER_BLOCK",
            preset.max_action_items_per_block,
        ),
        compressed_action_block_drop_protected_count=_env_int(
            env,
            "OASIS_V1_SUMMARY_COMPRESSED_ACTION_BLOCK_DROP_PROTECTED_COUNT",
            preset.compressed_action_block_drop_protected_count,
        ),
        max_action_items_per_recent_turn=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_ACTION_ITEMS_PER_RECENT_TURN",
            preset.max_action_items_per_recent_turn,
        ),
        max_authored_excerpt_chars=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_AUTHORED_EXCERPT_CHARS",
            preset.max_authored_excerpt_chars,
        ),
        max_target_summary_chars=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_TARGET_SUMMARY_CHARS",
            preset.max_target_summary_chars,
        ),
        max_local_context_chars=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_LOCAL_CONTEXT_CHARS",
            preset.max_local_context_chars,
        ),
        max_summary_merge_span=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_MERGE_SPAN",
            preset.max_summary_merge_span,
        ),
        max_heartbeat_entity_samples=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_HEARTBEAT_ENTITY_SAMPLES",
            preset.max_heartbeat_entity_samples,
        ),
        max_anchor_items_per_block=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_ANCHOR_ITEMS_PER_BLOCK",
            preset.max_anchor_items_per_block,
        ),
        max_entities_per_heartbeat=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_ENTITIES_PER_HEARTBEAT",
            preset.max_entities_per_heartbeat,
        ),
        max_state_changes_per_turn=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_STATE_CHANGES_PER_TURN",
            preset.max_state_changes_per_turn,
        ),
        max_outcome_digest_chars=_env_int(
            env,
            "OASIS_V1_SUMMARY_MAX_OUTCOME_DIGEST_CHARS",
            preset.max_outcome_digest_chars,
        ),
        compressed_note_title=_env_str(
            env,
            "OASIS_V1_SUMMARY_COMPRESSED_NOTE_TITLE",
            preset.compressed_note_title,
        ),
        recall_note_title=_env_str(
            env,
            "OASIS_V1_SUMMARY_RECALL_NOTE_TITLE",
            preset.recall_note_title,
        ),
        omit_empty_template_fields=_env_bool(
            env,
            "OASIS_V1_SUMMARY_OMIT_EMPTY_TEMPLATE_FIELDS",
            preset.omit_empty_template_fields,
        ),
    )


def apply_provider_runtime_env_overrides(
    preset: ProviderRuntimePresetConfig,
    *,
    environ: Mapping[str, str] | None = None,
) -> ProviderRuntimePresetConfig:
    env = environ or os.environ
    matcher_file = _env_str(
        env,
        "OASIS_V1_PROVIDER_ERROR_MATCHERS_FILE",
        "",
    )
    provider_error_matchers = preset.provider_error_matchers
    if matcher_file:
        provider_error_matchers = _merge_provider_error_matchers(
            provider_error_matchers,
            _load_provider_error_matchers(matcher_file),
        )
    return ProviderRuntimePresetConfig(
        provider_error_matchers=provider_error_matchers,
        provider_overflow_penalty_native_tiers=_env_tiers(
            env,
            "OASIS_V1_PROVIDER_NATIVE_OVERFLOW_TIERS",
            preset.provider_overflow_penalty_native_tiers,
        ),
        provider_overflow_penalty_heuristic_tiers=_env_tiers(
            env,
            "OASIS_V1_PROVIDER_HEURISTIC_OVERFLOW_TIERS",
            preset.provider_overflow_penalty_heuristic_tiers,
        ),
        counter_uncertainty_reserve_policy=_env_str(
            env,
            "OASIS_V1_PROVIDER_COUNTER_UNCERTAINTY_RESERVE_POLICY",
            preset.counter_uncertainty_reserve_policy,
        ),
        max_budget_retries=_env_int(
            env,
            "OASIS_V1_PROVIDER_MAX_BUDGET_RETRIES",
            preset.max_budget_retries,
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


def _env_bool(environ: Mapping[str, str], key: str, default: bool) -> bool:
    value = environ.get(key)
    if value in (None, ""):
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{key} must be a boolean-like value.")


def _env_str(environ: Mapping[str, str], key: str, default: str) -> str:
    value = environ.get(key)
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _env_tiers(
    environ: Mapping[str, str],
    key: str,
    default: tuple[tuple[int, float], ...],
) -> tuple[tuple[int, float], ...]:
    value = environ.get(key)
    if value in (None, ""):
        return default

    tiers: list[tuple[int, float]] = []
    for item in str(value).split(","):
        chunk = item.strip()
        if not chunk:
            continue
        minimum_raw, ratio_raw = chunk.split(":", maxsplit=1)
        tiers.append((int(minimum_raw.strip()), float(ratio_raw.strip())))
    if not tiers:
        raise ValueError(f"{key} must contain at least one tier.")
    return tuple(tiers)


def _load_provider_error_matchers(path: str) -> dict[str, ProviderMatcherFamily]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, Mapping):
        raise ValueError("provider matcher payload must be a mapping.")

    normalized: dict[str, ProviderMatcherFamily] = {}
    for provider, category_map in payload.items():
        if not isinstance(category_map, Mapping):
            raise ValueError("provider matcher categories must be mappings.")
        normalized[str(provider)] = _normalize_provider_matcher_family(category_map)
    return normalized


def _merge_provider_error_matchers(
    base: Mapping[str, Mapping[str, Any]],
    overlay: Mapping[str, Mapping[str, Any]],
) -> dict[str, ProviderMatcherFamily]:
    merged = {
        str(provider): _normalize_provider_matcher_family(category_map)
        for provider, category_map in base.items()
    }
    for provider, category_map in overlay.items():
        target = merged.setdefault(str(provider), _normalize_provider_matcher_family({}))
        normalized_family = _normalize_provider_matcher_family(category_map)
        target["structured"] = _merge_structured_matcher_section(
            target.get("structured", {}),
            normalized_family.get("structured", {}),
        )
        target["normalized_patterns"] = _merge_nested_matcher_section(
            target.get("normalized_patterns", {}),
            normalized_family.get("normalized_patterns", {}),
        )
        target["raw_patterns"] = _merge_nested_matcher_section(
            target.get("raw_patterns", {}),
            normalized_family.get("raw_patterns", {}),
        )
    return merged


def _normalize_provider_matcher_family(
    category_map: Mapping[str, Any],
) -> ProviderMatcherFamily:
    reserved_keys = {"structured", "normalized_patterns", "raw_patterns"}
    has_new_schema_key = any(key in category_map for key in reserved_keys)
    if not has_new_schema_key:
        return {
            "structured": {
                "status_codes": {},
                "error_codes": {},
                "exception_types": {},
            },
            "normalized_patterns": {
                str(category): _normalize_matcher_tuple(patterns, cast="str")
                for category, patterns in category_map.items()
            },
            "raw_patterns": {},
        }
    mixed_flat_keys = [
        str(key) for key in category_map.keys() if str(key) not in reserved_keys
    ]
    if mixed_flat_keys:
        raise ValueError(
            "provider matcher family cannot mix legacy flat categories with new-schema sections."
        )

    structured = category_map.get("structured", {}) or {}
    normalized_patterns = category_map.get("normalized_patterns", {}) or {}
    raw_patterns = category_map.get("raw_patterns", {}) or {}
    if not isinstance(structured, Mapping):
        raise ValueError("provider matcher structured section must be a mapping.")
    if not isinstance(normalized_patterns, Mapping):
        raise ValueError("provider matcher normalized_patterns section must be a mapping.")
    if not isinstance(raw_patterns, Mapping):
        raise ValueError("provider matcher raw_patterns section must be a mapping.")
    return {
        "structured": {
            "status_codes": {
                str(category): _normalize_matcher_tuple(patterns, cast="int")
                for category, patterns in (structured.get("status_codes", {}) or {}).items()
            },
            "error_codes": {
                str(category): _normalize_matcher_tuple(patterns, cast="str")
                for category, patterns in (structured.get("error_codes", {}) or {}).items()
            },
            "exception_types": {
                str(category): _normalize_matcher_tuple(patterns, cast="str")
                for category, patterns in (structured.get("exception_types", {}) or {}).items()
            },
        },
        "normalized_patterns": {
            str(category): _normalize_matcher_tuple(patterns, cast="str")
            for category, patterns in normalized_patterns.items()
        },
        "raw_patterns": {
            str(category): _normalize_matcher_tuple(patterns, cast="str")
            for category, patterns in raw_patterns.items()
        },
    }


def _normalize_matcher_tuple(
    patterns: Any,
    *,
    cast: str,
) -> MatcherTuple:
    if not isinstance(patterns, (list, tuple)):
        raise ValueError("provider matcher patterns must be a list.")
    if cast == "int":
        return tuple(int(pattern) for pattern in patterns)
    return tuple(str(pattern).strip() for pattern in patterns if str(pattern).strip())


def _merge_nested_matcher_section(
    base: Mapping[str, MatcherTuple],
    overlay: Mapping[str, MatcherTuple],
) -> MatcherCategoryMap:
    merged = {str(category): tuple(values) for category, values in base.items()}
    for category, values in overlay.items():
        merged[str(category)] = tuple(values)
    return merged


def _merge_structured_matcher_section(
    base: Mapping[str, Mapping[str, MatcherTuple]],
    overlay: Mapping[str, Mapping[str, MatcherTuple]],
) -> StructuredMatcherSection:
    merged = {
        str(section): {
            str(category): tuple(values)
            for category, values in categories.items()
        }
        for section, categories in base.items()
    }
    for section, categories in overlay.items():
        target = merged.setdefault(str(section), {})
        for category, values in categories.items():
            target[str(category)] = tuple(values)
    return merged
