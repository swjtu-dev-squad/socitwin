from pathlib import Path

from app.memory.config import (
    ProviderRuntimePresetConfig,
    RecallPresetConfig,
    SummaryPresetConfig,
    apply_provider_runtime_env_overrides,
    apply_recall_env_overrides,
    apply_summary_env_overrides,
)


def test_apply_recall_env_overrides_reads_legacy_envs() -> None:
    preset = apply_recall_env_overrides(
        RecallPresetConfig(),
        environ={
            "OASIS_V1_RECALL_LIMIT": "5",
            "OASIS_V1_RECALL_COOLDOWN_STEPS": "4",
            "OASIS_V1_RECALL_MIN_TRIGGER_ENTITY_COUNT": "2",
            "OASIS_V1_RECALL_ALLOW_TOPIC_TRIGGER": "false",
            "OASIS_V1_RECALL_ALLOW_ANCHOR_TRIGGER": "false",
            "OASIS_V1_RECALL_ALLOW_RECENT_ACTION_TRIGGER": "true",
            "OASIS_V1_RECALL_ALLOW_SELF_AUTHORED_TRIGGER": "false",
            "OASIS_V1_RECALL_DENY_REPEATED_QUERY_WITHIN_STEPS": "6",
            "OASIS_V1_RECALL_MAX_REASON_TRACE_CHARS": "77",
        },
    )

    assert preset.retrieval_limit == 5
    assert preset.cooldown_steps == 4
    assert preset.min_trigger_entity_count == 2
    assert preset.allow_topic_trigger is False
    assert preset.allow_anchor_trigger is False
    assert preset.allow_recent_action_trigger is True
    assert preset.allow_self_authored_trigger is False
    assert preset.deny_repeated_query_within_steps == 6
    assert preset.max_reason_trace_chars == 77


def test_apply_summary_env_overrides_reads_legacy_envs() -> None:
    preset = apply_summary_env_overrides(
        SummaryPresetConfig(),
        environ={
            "OASIS_V1_SUMMARY_MAX_ACTION_ITEMS_PER_BLOCK": "9",
            "OASIS_V1_SUMMARY_MAX_MERGE_SPAN": "5",
            "OASIS_V1_SUMMARY_COMPRESSED_ACTION_BLOCK_DROP_PROTECTED_COUNT": "4",
            "OASIS_V1_SUMMARY_MAX_ACTION_ITEMS_PER_RECENT_TURN": "8",
            "OASIS_V1_SUMMARY_MAX_AUTHORED_EXCERPT_CHARS": "140",
            "OASIS_V1_SUMMARY_MAX_TARGET_SUMMARY_CHARS": "150",
            "OASIS_V1_SUMMARY_MAX_LOCAL_CONTEXT_CHARS": "160",
            "OASIS_V1_SUMMARY_MAX_HEARTBEAT_ENTITY_SAMPLES": "6",
            "OASIS_V1_SUMMARY_MAX_ANCHOR_ITEMS_PER_BLOCK": "7",
            "OASIS_V1_SUMMARY_MAX_ENTITIES_PER_HEARTBEAT": "8",
            "OASIS_V1_SUMMARY_MAX_STATE_CHANGES_PER_TURN": "9",
            "OASIS_V1_SUMMARY_MAX_OUTCOME_DIGEST_CHARS": "170",
            "OASIS_V1_SUMMARY_COMPRESSED_NOTE_TITLE": "Compressed memory",
            "OASIS_V1_SUMMARY_RECALL_NOTE_TITLE": "Long-term memory",
            "OASIS_V1_SUMMARY_OMIT_EMPTY_TEMPLATE_FIELDS": "false",
        },
    )

    assert preset.max_action_items_per_block == 9
    assert preset.max_summary_merge_span == 5
    assert preset.compressed_action_block_drop_protected_count == 4
    assert preset.max_action_items_per_recent_turn == 8
    assert preset.max_authored_excerpt_chars == 140
    assert preset.max_target_summary_chars == 150
    assert preset.max_local_context_chars == 160
    assert preset.max_heartbeat_entity_samples == 6
    assert preset.max_anchor_items_per_block == 7
    assert preset.max_entities_per_heartbeat == 8
    assert preset.max_state_changes_per_turn == 9
    assert preset.max_outcome_digest_chars == 170
    assert preset.compressed_note_title == "Compressed memory"
    assert preset.recall_note_title == "Long-term memory"
    assert preset.omit_empty_template_fields is False


def test_apply_provider_runtime_env_overrides_reads_legacy_envs(tmp_path: Path) -> None:
    matcher_file = tmp_path / "provider_matchers.json"
    matcher_file.write_text(
        '{"custom":{"normalized_patterns":{"context_overflow":["custom overflow"]}}}',
        encoding="utf-8",
    )

    preset = apply_provider_runtime_env_overrides(
        ProviderRuntimePresetConfig(),
        environ={
            "OASIS_V1_PROVIDER_ERROR_MATCHERS_FILE": str(matcher_file),
            "OASIS_V1_PROVIDER_NATIVE_OVERFLOW_TIERS": "128:0.02,256:0.05",
            "OASIS_V1_PROVIDER_HEURISTIC_OVERFLOW_TIERS": "512:0.08,1024:0.16",
            "OASIS_V1_PROVIDER_COUNTER_UNCERTAINTY_RESERVE_POLICY": "none",
            "OASIS_V1_PROVIDER_MAX_BUDGET_RETRIES": "6",
        },
    )

    assert preset.provider_error_matchers["custom"]["normalized_patterns"][
        "context_overflow"
    ] == ("custom overflow",)
    assert preset.provider_overflow_penalty_native_tiers == ((128, 0.02), (256, 0.05))
    assert preset.provider_overflow_penalty_heuristic_tiers == (
        (512, 0.08),
        (1024, 0.16),
    )
    assert preset.counter_uncertainty_reserve_policy == "none"
    assert preset.max_budget_retries == 6
