from camel.messages import BaseMessage

from app.memory.budget_recovery import BudgetRecoveryController
from app.memory.config import (
    ActionV1RuntimeSettings,
    ObservationPresetConfig,
    ProviderRuntimePresetConfig,
    SummaryPresetConfig,
    TokenCounterLike,
    WorkingMemoryBudgetConfig,
)


class FixedTokenCounter(TokenCounterLike):
    def count_tokens_from_messages(self, messages) -> int:
        return sum(max(1, len(str(message.get("content", ""))) // 8) for message in messages)


def _settings(**overrides) -> ActionV1RuntimeSettings:
    provider_runtime_preset = overrides.pop(
        "provider_runtime_preset",
        ProviderRuntimePresetConfig(max_budget_retries=4),
    )
    return ActionV1RuntimeSettings(
        token_counter=FixedTokenCounter(),
        system_message=BaseMessage.make_assistant_message(
            role_name="system",
            content="system prompt",
        ),
        context_token_limit=4096,
        observation_preset=ObservationPresetConfig(),
        working_memory_budget=WorkingMemoryBudgetConfig(
            generation_reserve_tokens=512,
        ),
        summary_preset=SummaryPresetConfig(),
        provider_runtime_preset=provider_runtime_preset,
        **overrides,
    )


def test_effective_prompt_budget_subtracts_generation_reserve() -> None:
    controller = BudgetRecoveryController(_settings())
    state = controller.initial_state()

    assert controller.effective_prompt_budget(state=state) == 4096 - 512


def test_provider_overflow_adds_generation_reserve_penalty_after_repeated_overflow() -> None:
    controller = BudgetRecoveryController(_settings())
    state = controller.initial_state()

    first = controller.next_for_provider_overflow(state=state)
    assert first is not None
    assert first.generation_reserve_penalty == 0

    second = controller.next_for_provider_overflow(state=first)
    assert second is not None
    assert second.generation_reserve_penalty == 128
    assert controller.effective_prompt_budget(state=second) == 4096 - 512 - 128


def test_local_over_budget_follows_v1_stage_order_without_recent_shrink() -> None:
    controller = BudgetRecoveryController(
        _settings(
            provider_runtime_preset=ProviderRuntimePresetConfig(
                max_budget_retries=4,
            ),
        )
    )
    state = controller.initial_state()
    stages = []
    observation_levels = []

    for _ in range(4):
        state = controller.next_for_local_over_budget(state=state)
        assert state is not None
        stages.append(state.stage)
        observation_levels.append(state.observation_reduction_level)
        assert state.recent_step_cap_override is None

    assert stages == [
        "drop_recall",
        "drop_compressed",
        "strong_observation_reduction",
        "minimal_physical_fallback",
    ]
    assert observation_levels == [0, 0, 1, 2]
    assert controller.next_for_local_over_budget(state=state) is None


def test_local_over_budget_drops_recall_then_compressed() -> None:
    controller = BudgetRecoveryController(_settings())
    state = controller.initial_state()

    first = controller.next_for_local_over_budget(state=state)
    assert first is not None
    second = controller.next_for_local_over_budget(state=first)
    assert second is not None

    assert first.include_recall is False
    assert first.include_compressed is True
    assert second.include_recall is False
    assert second.include_compressed is False
