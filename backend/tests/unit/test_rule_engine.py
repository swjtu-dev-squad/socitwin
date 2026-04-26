"""
Tests for the RuleEngine - rule-based action selection and condition evaluation.
"""

from unittest.mock import MagicMock

import pytest

from app.models.behavior import (
    BehaviorContext,
    BehaviorRule,
    ConditionOperator,
    RuleCondition,
)
from app.models.simulation import OASISActionType, PlatformType

# ============================================================================
# Mock helpers
# ============================================================================


def make_mock_agent(agent_id=0):
    agent = MagicMock()
    agent.social_agent_id = agent_id
    return agent


def make_context(**kwargs):
    defaults = {
        "current_step": 0,
        "platform": PlatformType.TWITTER,
        "agent_id": 0,
    }
    defaults.update(kwargs)
    return BehaviorContext(**defaults)


# ============================================================================
# RuleEngine condition evaluation tests
# ============================================================================


class TestConditionEvaluation:
    def test_equals_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="current_step", operator=ConditionOperator.EQUALS, value=0)
        ctx = make_context(current_step=0).model_dump()
        assert engine._evaluate_condition(cond, ctx) is True
        assert engine._evaluate_condition(cond, make_context(current_step=1).model_dump()) is False

    def test_not_equals_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="current_step", operator=ConditionOperator.NOT_EQUALS, value=0)
        ctx = make_context(current_step=1).model_dump()
        assert engine._evaluate_condition(cond, ctx) is True
        assert engine._evaluate_condition(cond, make_context(current_step=0).model_dump()) is False

    def test_greater_than_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="current_step", operator=ConditionOperator.GREATER_THAN, value=5)
        assert engine._evaluate_condition(cond, make_context(current_step=10).model_dump()) is True
        assert engine._evaluate_condition(cond, make_context(current_step=5).model_dump()) is False

    def test_less_than_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="current_step", operator=ConditionOperator.LESS_THAN, value=5)
        assert engine._evaluate_condition(cond, make_context(current_step=3).model_dump()) is True
        assert engine._evaluate_condition(cond, make_context(current_step=7).model_dump()) is False

    def test_greater_than_or_equal_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(
            field="current_step",
            operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
            value=5,
        )
        assert engine._evaluate_condition(cond, make_context(current_step=5).model_dump()) is True
        assert engine._evaluate_condition(cond, make_context(current_step=4).model_dump()) is False

    def test_less_than_or_equal_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(
            field="current_step",
            operator=ConditionOperator.LESS_THAN_OR_EQUAL,
            value=5,
        )
        assert engine._evaluate_condition(cond, make_context(current_step=5).model_dump()) is True
        assert engine._evaluate_condition(cond, make_context(current_step=6).model_dump()) is False

    def test_contains_operator_string(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="platform", operator=ConditionOperator.CONTAINS, value="wit")
        ctx = make_context(platform=PlatformType.TWITTER).model_dump()
        assert engine._evaluate_condition(cond, ctx) is True

    def test_not_contains_operator_string(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="platform", operator=ConditionOperator.NOT_CONTAINS, value="red")
        ctx = make_context(platform=PlatformType.TWITTER).model_dump()
        assert engine._evaluate_condition(cond, ctx) is True

    def test_starts_with_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        ctx = make_context(platform=PlatformType.TWITTER).model_dump()
        cond = RuleCondition(field="platform", operator=ConditionOperator.STARTS_WITH, value="tw")
        assert engine._evaluate_condition(cond, ctx) is True
        cond2 = RuleCondition(field="platform", operator=ConditionOperator.STARTS_WITH, value="re")
        assert engine._evaluate_condition(cond2, ctx) is False

    def test_ends_with_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        ctx = make_context(platform=PlatformType.TWITTER).model_dump()
        cond = RuleCondition(field="platform", operator=ConditionOperator.ENDS_WITH, value="ter")
        assert engine._evaluate_condition(cond, ctx) is True
        cond2 = RuleCondition(field="platform", operator=ConditionOperator.ENDS_WITH, value="dit")
        assert engine._evaluate_condition(cond2, ctx) is False

    def test_in_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        ctx = make_context(platform=PlatformType.TWITTER).model_dump()
        cond = RuleCondition(
            field="platform",
            operator=ConditionOperator.IN,
            value=["twitter", "reddit"],
        )
        assert engine._evaluate_condition(cond, ctx) is True

    def test_not_in_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        ctx = make_context(platform=PlatformType.TWITTER).model_dump()
        cond = RuleCondition(
            field="platform",
            operator=ConditionOperator.NOT_IN,
            value=["facebook", "instagram"],
        )
        assert engine._evaluate_condition(cond, ctx) is True

    def test_exists_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="current_step", operator=ConditionOperator.EXISTS)
        ctx = make_context(current_step=0).model_dump()
        assert engine._evaluate_condition(cond, ctx) is True

    def test_not_exists_operator(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="nonexistent_field", operator=ConditionOperator.NOT_EXISTS)
        ctx = make_context().model_dump()
        assert engine._evaluate_condition(cond, ctx) is True

    def test_field_not_in_context(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        cond = RuleCondition(field="missing_field", operator=ConditionOperator.EQUALS, value=1)
        ctx = make_context().model_dump()
        assert engine._evaluate_condition(cond, ctx) is False

    def test_compare_values_numeric(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        assert engine._compare_values(5, 3) == 1
        assert engine._compare_values(3, 5) == -1
        assert engine._compare_values(3, 3) == 0

    def test_compare_values_numeric_from_strings(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        assert engine._compare_values("5", "3") == 1

    def test_compare_values_string_fallback(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        assert engine._compare_values("apple", "banana") < 0
        assert engine._compare_values("banana", "apple") > 0
        assert engine._compare_values("apple", "apple") == 0


# ============================================================================
# RuleEngine rule evaluation tests
# ============================================================================


class TestRuleEvaluation:
    def test_no_rules_returns_none(self):
        import asyncio

        from app.core.rule_engine import RuleEngine

        engine = RuleEngine([])
        agent = make_mock_agent()
        context = make_context()

        result = asyncio.run(engine.evaluate_rules(agent, context))
        assert result is None

    def test_rule_with_no_conditions_always_triggers(self):
        import asyncio

        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="always",
            name="Always Trigger",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        engine = RuleEngine([rule])
        agent = make_mock_agent()
        context = make_context()

        result = asyncio.run(engine.evaluate_rules(agent, context))
        assert result is not None

    def test_disabled_rule_does_not_trigger(self):
        import asyncio

        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="disabled",
            name="Disabled Rule",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=False,
        )
        engine = RuleEngine([rule])
        agent = make_mock_agent()
        context = make_context()

        result = asyncio.run(engine.evaluate_rules(agent, context))
        assert result is None

    def test_rule_with_conditions_met(self):
        import asyncio

        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="step_check",
            name="Step Check",
            priority=1,
            conditions=[
                RuleCondition(
                    field="current_step", operator=ConditionOperator.GREATER_THAN, value=0
                ),
            ],
            action=OASISActionType.LIKE_POST,
        )
        engine = RuleEngine([rule])
        agent = make_mock_agent()
        context = make_context(current_step=1)

        result = asyncio.run(engine.evaluate_rules(agent, context))
        assert result is not None

    def test_rule_with_conditions_not_met(self):
        import asyncio

        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="step_check",
            name="Step Check",
            priority=1,
            conditions=[
                RuleCondition(
                    field="current_step", operator=ConditionOperator.GREATER_THAN, value=5
                ),
            ],
            action=OASISActionType.LIKE_POST,
        )
        engine = RuleEngine([rule])
        agent = make_mock_agent()
        context = make_context(current_step=1)

        result = asyncio.run(engine.evaluate_rules(agent, context))
        assert result is None

    def test_rule_action_includes_agent_context(self):
        import asyncio

        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="ctx_test",
            name="Context Test",
            priority=1,
            action=OASISActionType.CREATE_COMMENT,
        )
        engine = RuleEngine([rule])
        agent = make_mock_agent(agent_id=42)
        context = make_context(current_step=5, agent_id=42)

        result = asyncio.run(engine.evaluate_rules(agent, context))
        assert result is not None
        assert result.action_args["agent_id"] == 42
        assert result.action_args["step"] == 5

    def test_higher_priority_rule_triggers_first(self):

        from app.core.rule_engine import RuleEngine

        low_priority = BehaviorRule(
            rule_id="low",
            name="Low Priority",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        high_priority = BehaviorRule(
            rule_id="high",
            name="High Priority",
            priority=10,
            action=OASISActionType.LIKE_POST,
        )
        engine = RuleEngine([low_priority, high_priority])

        # _sorted_rules should have high priority first
        assert engine._sorted_rules[0].rule_id == "high"
        assert engine._sorted_rules[1].rule_id == "low"


# ============================================================================
# RuleEngine rule management tests
# ============================================================================


class TestRuleManagement:
    def test_update_rules(self):
        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="test",
            name="Test",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        engine = RuleEngine()
        engine.update_rules([rule])
        assert len(engine.rules) == 1

    def test_add_rule(self):
        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="new_rule",
            name="New",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        engine = RuleEngine()
        engine.add_rule(rule)
        assert len(engine.rules) == 1

    def test_add_duplicate_rule_id_replaces(self):
        from app.core.rule_engine import RuleEngine

        rule1 = BehaviorRule(
            rule_id="same",
            name="First",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        rule2 = BehaviorRule(
            rule_id="same",
            name="Second",
            priority=5,
            action=OASISActionType.LIKE_POST,
        )
        engine = RuleEngine([rule1])
        engine.add_rule(rule2)
        assert len(engine.rules) == 1
        assert engine.rules[0].name == "Second"

    def test_remove_rule(self):
        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="to_remove",
            name="Remove Me",
            priority=1,
            action=OASISActionType.DO_NOTHING,
        )
        engine = RuleEngine([rule])
        assert engine.remove_rule("to_remove") is True
        assert len(engine.rules) == 0

    def test_remove_nonexistent_rule(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        assert engine.remove_rule("nonexistent") is False

    def test_enable_disable_rule(self):
        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="toggle",
            name="Toggle",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=False,
        )
        engine = RuleEngine([rule])
        assert engine.enable_rule("toggle") is True
        assert engine.get_rule("toggle").enabled is True
        assert engine.disable_rule("toggle") is True
        assert engine.get_rule("toggle").enabled is False

    def test_get_rule(self):
        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="find_me",
            name="Find Me",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        engine = RuleEngine([rule])
        assert engine.get_rule("find_me") is not None
        assert engine.get_rule("not_there") is None

    def test_clear_rules(self):
        from app.core.rule_engine import RuleEngine

        rule = BehaviorRule(
            rule_id="r1",
            name="R1",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        engine = RuleEngine([rule])
        engine.clear_rules()
        assert len(engine.rules) == 0

    def test_get_enabled_rules(self):
        from app.core.rule_engine import RuleEngine

        r1 = BehaviorRule(
            rule_id="e1",
            name="E1",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=True,
        )
        r2 = BehaviorRule(
            rule_id="d1",
            name="D1",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=False,
        )
        engine = RuleEngine([r1, r2])
        enabled = engine.get_enabled_rules()
        assert len(enabled) == 1
        assert enabled[0].rule_id == "e1"

    def test_get_disabled_rules(self):
        from app.core.rule_engine import RuleEngine

        r1 = BehaviorRule(
            rule_id="e1",
            name="E1",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=True,
        )
        r2 = BehaviorRule(
            rule_id="d1",
            name="D1",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=False,
        )
        engine = RuleEngine([r1, r2])
        disabled = engine.get_disabled_rules()
        assert len(disabled) == 1
        assert disabled[0].rule_id == "d1"


# ============================================================================
# RuleEngine validation tests
# ============================================================================


class TestRuleValidation:
    def test_empty_rule_id_raises(self):
        from app.core.rule_engine import InvalidRuleError, RuleEngine

        engine = RuleEngine()
        # Bypass model-level validation to test engine-level validation
        rule = BehaviorRule(
            rule_id="x", name="Test", priority=1, action=OASISActionType.CREATE_POST
        )
        rule.rule_id = ""
        with pytest.raises(InvalidRuleError):
            engine._validate_single_rule(rule)

    def test_priority_out_of_range(self):
        from app.core.rule_engine import InvalidRuleError, RuleEngine

        engine = RuleEngine()
        rule = BehaviorRule(
            rule_id="test", name="Test", priority=1, action=OASISActionType.CREATE_POST
        )
        rule.priority = 0
        with pytest.raises(InvalidRuleError):
            engine._validate_single_rule(rule)

    def test_duplicate_ids_in_batch(self):
        from app.core.rule_engine import InvalidRuleError, RuleEngine

        engine = RuleEngine()
        with pytest.raises(InvalidRuleError):
            engine._validate_rules(
                [
                    BehaviorRule(
                        rule_id="dup", name="A", priority=1, action=OASISActionType.CREATE_POST
                    ),
                    BehaviorRule(
                        rule_id="dup", name="B", priority=1, action=OASISActionType.LIKE_POST
                    ),
                ]
            )

    def test_invalid_action_type(self):
        from app.core.rule_engine import InvalidRuleError, RuleEngine

        engine = RuleEngine()
        rule = BehaviorRule(
            rule_id="test", name="Test", priority=1, action=OASISActionType.CREATE_POST
        )
        # Change to something that can't be mapped to ActionType
        rule.action = MagicMock()
        rule.action.value = "INVALID_ACTION_TYPE"
        with pytest.raises(InvalidRuleError):
            engine._validate_single_rule(rule)


# ============================================================================
# RuleEngine statistics tests
# ============================================================================


class TestRuleStatistics:
    def test_get_statistics(self):
        from app.core.rule_engine import RuleEngine

        r1 = BehaviorRule(
            rule_id="s1",
            name="Stats 1",
            priority=1,
            action=OASISActionType.CREATE_POST,
            enabled=True,
        )
        engine = RuleEngine([r1])
        stats = engine.get_statistics()
        assert stats["total_rules"] == 1
        assert stats["enabled_rules"] == 1
        assert stats["disabled_rules"] == 0

    def test_reset_statistics(self):
        from app.core.rule_engine import RuleEngine

        engine = RuleEngine()
        engine.total_evaluations = 100
        engine.rule_evaluation_counts = {"r1": 50}
        engine.reset_statistics()
        assert engine.total_evaluations == 0
        assert engine.rule_evaluation_counts == {}
