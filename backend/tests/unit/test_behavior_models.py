"""
Tests for behavior models - Pydantic schemas validation and factory functions.
"""

import pytest

from app.models.behavior import (
    ActionProbability,
    AgentBehaviorConfig,
    BehaviorContext,
    BehaviorRule,
    BehaviorSchedule,
    BehaviorStrategy,
    ConditionOperator,
    MixedStrategyConfig,
    ProbabilityDistribution,
    RuleCondition,
    RuleSet,
    StrategyWeight,
    TimelineEvent,
    create_default_behavior_config,
    create_probabilistic_config,
    create_rule_based_config,
    create_scheduled_config,
)
from app.models.simulation import OASISActionType, PlatformType

# ============================================================================
# ActionProbability tests
# ============================================================================


class TestActionProbability:
    def test_valid_action_probability(self):
        ap = ActionProbability(
            action_type=OASISActionType.CREATE_POST,
            probability=0.5,
        )
        assert ap.action_type == OASISActionType.CREATE_POST
        assert ap.probability == 0.5
        assert ap.conditions is None
        assert ap.action_args == {}

    def test_probability_bounds(self):
        ActionProbability(action_type=OASISActionType.CREATE_POST, probability=0.0)
        ActionProbability(action_type=OASISActionType.CREATE_POST, probability=1.0)

    def test_probability_out_of_bounds_raises(self):
        with pytest.raises(ValueError):
            ActionProbability(action_type=OASISActionType.CREATE_POST, probability=-0.1)
        with pytest.raises(ValueError):
            ActionProbability(action_type=OASISActionType.CREATE_POST, probability=1.1)

    def test_with_conditions(self):
        ap = ActionProbability(
            action_type=OASISActionType.LIKE_POST,
            probability=0.3,
            conditions={"sentiment": "positive", "time_of_day": "morning"},
        )
        assert ap.conditions == {"sentiment": "positive", "time_of_day": "morning"}

    def test_with_action_args(self):
        ap = ActionProbability(
            action_type=OASISActionType.CREATE_COMMENT,
            probability=0.4,
            action_args={"template": "Interesting post!"},
        )
        assert ap.action_args == {"template": "Interesting post!"}


# ============================================================================
# ProbabilityDistribution tests
# ============================================================================


class TestProbabilityDistribution:
    def test_valid_distribution(self):
        actions = [
            ActionProbability(action_type=OASISActionType.CREATE_POST, probability=0.3),
            ActionProbability(action_type=OASISActionType.LIKE_POST, probability=0.7),
        ]
        dist = ProbabilityDistribution(name="test", actions=actions)
        assert dist.name == "test"
        assert len(dist.actions) == 2

    def test_auto_normalize_distribution(self):
        # Probabilities within [0,1] but not summing to 1.0 get normalized
        actions = [
            ActionProbability(action_type=OASISActionType.CREATE_POST, probability=0.3),
            ActionProbability(action_type=OASISActionType.LIKE_POST, probability=0.5),
        ]
        dist = ProbabilityDistribution(name="test", actions=actions)
        total = sum(a.probability for a in dist.actions)
        assert abs(total - 1.0) < 0.01

    def test_zero_probabilities_get_equal_distribution(self):
        actions = [
            ActionProbability(action_type=OASISActionType.CREATE_POST, probability=0.0),
            ActionProbability(action_type=OASISActionType.LIKE_POST, probability=0.0),
            ActionProbability(action_type=OASISActionType.REFRESH, probability=0.0),
        ]
        dist = ProbabilityDistribution(name="test", actions=actions)
        for a in dist.actions:
            assert abs(a.probability - 1.0 / 3) < 0.01

    def test_empty_actions(self):
        dist = ProbabilityDistribution(name="test", actions=[])
        assert dist.actions == []

    def test_with_platform(self):
        dist = ProbabilityDistribution(name="test", actions=[], platform=PlatformType.TWITTER)
        assert dist.platform == PlatformType.TWITTER


# ============================================================================
# RuleCondition tests
# ============================================================================


class TestRuleCondition:
    def test_valid_condition(self):
        cond = RuleCondition(
            field="current_step",
            operator=ConditionOperator.GREATER_THAN,
            value=10,
        )
        assert cond.field == "current_step"
        assert cond.operator == ConditionOperator.GREATER_THAN
        assert cond.value == 10

    def test_exists_operator_without_value(self):
        cond = RuleCondition(
            field="some_field",
            operator=ConditionOperator.EXISTS,
        )
        assert cond.value is None

    def test_in_operator_with_list(self):
        cond = RuleCondition(
            field="platform",
            operator=ConditionOperator.IN,
            value=["twitter", "reddit"],
        )
        assert cond.value == ["twitter", "reddit"]


# ============================================================================
# BehaviorRule tests
# ============================================================================


class TestBehaviorRule:
    def test_valid_rule(self):
        rule = BehaviorRule(
            rule_id="test_rule",
            name="Test Rule",
            priority=5,
            action=OASISActionType.CREATE_POST,
        )
        assert rule.rule_id == "test_rule"
        assert rule.enabled is True
        assert rule.conditions == []

    def test_rule_id_lowercase(self):
        rule = BehaviorRule(
            rule_id="UPPERCASE_ID",
            name="Test",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        assert rule.rule_id == "uppercase_id"

    def test_rule_id_special_chars(self):
        with pytest.raises(ValueError):
            BehaviorRule(
                rule_id="invalid id!",
                name="Test",
                priority=1,
                action=OASISActionType.CREATE_POST,
            )

    def test_priority_bounds(self):
        BehaviorRule(
            rule_id="min_priority",
            name="Test",
            priority=1,
            action=OASISActionType.CREATE_POST,
        )
        BehaviorRule(
            rule_id="max_priority",
            name="Test",
            priority=10,
            action=OASISActionType.CREATE_POST,
        )

    def test_priority_out_of_bounds_raises(self):
        with pytest.raises(ValueError):
            BehaviorRule(
                rule_id="low",
                name="Test",
                priority=0,
                action=OASISActionType.CREATE_POST,
            )
        with pytest.raises(ValueError):
            BehaviorRule(
                rule_id="high",
                name="Test",
                priority=11,
                action=OASISActionType.CREATE_POST,
            )

    def test_rule_with_conditions(self):
        rule = BehaviorRule(
            rule_id="conditional_rule",
            name="Conditional Rule",
            priority=3,
            conditions=[
                RuleCondition(field="step", operator=ConditionOperator.GREATER_THAN, value=0),
                RuleCondition(field="platform", operator=ConditionOperator.EQUALS, value="twitter"),
            ],
            action=OASISActionType.CREATE_COMMENT,
        )
        assert len(rule.conditions) == 2

    def test_disabled_rule(self):
        rule = BehaviorRule(
            rule_id="disabled_rule",
            name="Disabled",
            priority=1,
            action=OASISActionType.DO_NOTHING,
            enabled=False,
        )
        assert rule.enabled is False

    def test_rule_with_action_args(self):
        rule = BehaviorRule(
            rule_id="with_args",
            name="With Args",
            priority=1,
            action=OASISActionType.CREATE_POST,
            action_args={"content": "Hello!"},
        )
        assert rule.action_args == {"content": "Hello!"}


# ============================================================================
# RuleSet tests
# ============================================================================


class TestRuleSet:
    def test_valid_rule_set(self):
        rules = [
            BehaviorRule(
                rule_id="r1",
                name="Rule 1",
                priority=1,
                action=OASISActionType.CREATE_POST,
            ),
            BehaviorRule(
                rule_id="r2",
                name="Rule 2",
                priority=2,
                action=OASISActionType.LIKE_POST,
            ),
        ]
        rs = RuleSet(name="test_set", rules=rules)
        assert rs.name == "test_set"
        assert len(rs.rules) == 2

    def test_empty_rule_set(self):
        rs = RuleSet(name="empty_set")
        assert rs.rules == []


# ============================================================================
# TimelineEvent tests
# ============================================================================


class TestTimelineEvent:
    def test_valid_event(self):
        event = TimelineEvent(step=0, action=OASISActionType.CREATE_POST)
        assert event.step == 0
        assert event.action == OASISActionType.CREATE_POST
        assert event.repeat_interval is None
        assert event.repeat_count is None

    def test_negative_step_raises(self):
        with pytest.raises(ValueError):
            TimelineEvent(step=-1, action=OASISActionType.CREATE_POST)

    def test_repeat_event(self):
        event = TimelineEvent(
            step=5,
            action=OASISActionType.LIKE_POST,
            repeat_interval=3,
            repeat_count=10,
        )
        assert event.repeat_interval == 3
        assert event.repeat_count == 10

    def test_repeat_interval_must_be_positive(self):
        with pytest.raises(ValueError):
            TimelineEvent(
                step=0,
                action=OASISActionType.CREATE_POST,
                repeat_interval=0,
            )

    def test_event_with_action_args(self):
        event = TimelineEvent(
            step=0,
            action=OASISActionType.CREATE_POST,
            action_args={"content": "Hello world"},
        )
        assert event.action_args == {"content": "Hello world"}


# ============================================================================
# BehaviorSchedule tests
# ============================================================================


class TestBehaviorSchedule:
    def test_valid_schedule(self):
        timeline = [
            TimelineEvent(step=0, action=OASISActionType.CREATE_POST),
            TimelineEvent(step=5, action=OASISActionType.LIKE_POST),
        ]
        schedule = BehaviorSchedule(name="test_schedule", timeline=timeline)
        assert schedule.name == "test_schedule"
        assert len(schedule.timeline) == 2
        assert schedule.loop is False

    def test_looping_schedule(self):
        schedule = BehaviorSchedule(name="loop_schedule", timeline=[], loop=True)
        assert schedule.loop is True


# ============================================================================
# StrategyWeight tests
# ============================================================================


class TestStrategyWeight:
    def test_valid_weight(self):
        sw = StrategyWeight(strategy=BehaviorStrategy.PROBABILISTIC, weight=0.6)
        assert sw.strategy == BehaviorStrategy.PROBABILISTIC
        assert sw.weight == 0.6

    def test_weight_out_of_bounds_raises(self):
        with pytest.raises(ValueError):
            StrategyWeight(strategy=BehaviorStrategy.RULE_BASED, weight=1.5)
        with pytest.raises(ValueError):
            StrategyWeight(strategy=BehaviorStrategy.SCHEDULED, weight=-0.1)


# ============================================================================
# MixedStrategyConfig tests
# ============================================================================


class TestMixedStrategyConfig:
    def test_valid_mixed_config(self):
        weights = [
            StrategyWeight(strategy=BehaviorStrategy.PROBABILISTIC, weight=0.4),
            StrategyWeight(strategy=BehaviorStrategy.RULE_BASED, weight=0.6),
        ]
        config = MixedStrategyConfig(name="mixed1", strategy_weights=weights)
        assert config.name == "mixed1"
        assert config.selection_mode == "weighted_random"

    def test_auto_normalize_weights(self):
        weights = [
            StrategyWeight(strategy=BehaviorStrategy.PROBABILISTIC, weight=1.0),
            StrategyWeight(strategy=BehaviorStrategy.RULE_BASED, weight=1.0),
        ]
        config = MixedStrategyConfig(name="mixed2", strategy_weights=weights)
        total = sum(w.weight for w in config.strategy_weights)
        assert abs(total - 1.0) < 0.01

    def test_equal_weights_if_all_zero(self):
        weights = [
            StrategyWeight(strategy=BehaviorStrategy.PROBABILISTIC, weight=0.0),
            StrategyWeight(strategy=BehaviorStrategy.RULE_BASED, weight=0.0),
        ]
        config = MixedStrategyConfig(name="mixed3", strategy_weights=weights)
        for w in config.strategy_weights:
            assert abs(w.weight - 0.5) < 0.01


# ============================================================================
# AgentBehaviorConfig tests
# ============================================================================


class TestAgentBehaviorConfig:
    def test_default_config(self):
        config = AgentBehaviorConfig()
        assert config.strategy == BehaviorStrategy.LLM_AUTONOMOUS
        assert config.enabled is True

    def test_is_active_when_enabled(self):
        config = AgentBehaviorConfig(enabled=True)
        assert config.is_active({"current_step": 0}) is True

    def test_is_active_when_disabled(self):
        config = AgentBehaviorConfig(enabled=False)
        assert config.is_active({"current_step": 0}) is False

    def test_platform_filter(self):
        config = AgentBehaviorConfig(platform_filter=PlatformType.TWITTER, enabled=True)
        assert config.is_active({"platform": PlatformType.TWITTER, "current_step": 0}) is True
        assert config.is_active({"platform": PlatformType.REDDIT, "current_step": 0}) is False

    def test_step_range(self):
        config = AgentBehaviorConfig(step_range=(5, 10), enabled=True)
        assert config.is_active({"current_step": 5}) is True
        assert config.is_active({"current_step": 10}) is True
        assert config.is_active({"current_step": 4}) is False
        assert config.is_active({"current_step": 11}) is False

    def test_additional_conditions(self):
        config = AgentBehaviorConfig(conditions={"event_type": "mentioned"}, enabled=True)
        assert config.is_active({"event_type": "mentioned", "current_step": 0}) is True
        assert config.is_active({"event_type": "other", "current_step": 0}) is False

    def test_step_range_validation(self):
        config = AgentBehaviorConfig(step_range=(0, 10))
        assert config.step_range == (0, 10)

    def test_step_range_invalid(self):
        with pytest.raises(ValueError):
            AgentBehaviorConfig(step_range=(10, 5))


# ============================================================================
# BehaviorContext tests
# ============================================================================


class TestBehaviorContext:
    def test_minimal_context(self):
        ctx = BehaviorContext(
            current_step=0,
            platform=PlatformType.TWITTER,
            agent_id=1,
        )
        assert ctx.current_step == 0
        assert ctx.platform == PlatformType.TWITTER
        assert ctx.agent_id == 1
        assert ctx.recent_actions == []

    def test_full_context(self):
        ctx = BehaviorContext(
            current_step=10,
            platform=PlatformType.REDDIT,
            agent_id=42,
            agent_state={"mood": "happy"},
            simulation_state={"total_agents": 100},
            recent_actions=[{"action": "CREATE_POST", "step": 9}],
        )
        assert ctx.agent_state == {"mood": "happy"}
        assert len(ctx.recent_actions) == 1


# ============================================================================
# Factory function tests
# ============================================================================


class TestFactoryFunctions:
    def test_create_default_config(self):
        config = create_default_behavior_config()
        assert config.strategy == BehaviorStrategy.LLM_AUTONOMOUS
        assert config.enabled is True

    def test_create_probabilistic_config_twitter(self):
        config = create_probabilistic_config("test", PlatformType.TWITTER)
        assert config.strategy == BehaviorStrategy.PROBABILISTIC
        assert config.probability_distribution is not None
        assert len(config.probability_distribution.actions) == 5

    def test_create_probabilistic_config_reddit(self):
        config = create_probabilistic_config("test", PlatformType.REDDIT)
        assert config.strategy == BehaviorStrategy.PROBABILISTIC
        assert config.probability_distribution is not None
        assert len(config.probability_distribution.actions) == 6

    def test_create_scheduled_config(self):
        config = create_scheduled_config("campaign", PlatformType.TWITTER)
        assert config.strategy == BehaviorStrategy.SCHEDULED
        assert config.schedule is not None
        assert len(config.schedule.timeline) == 4
        assert config.schedule.loop is False

    def test_create_rule_based_config(self):
        config = create_rule_based_config("support", PlatformType.TWITTER)
        assert config.strategy == BehaviorStrategy.RULE_BASED
        assert config.rule_set is not None
        assert len(config.rule_set.rules) == 3
        # Verify all expected rule IDs exist
        rule_ids = {r.rule_id for r in config.rule_set.rules}
        assert "respond_to_mentions" in rule_ids
        assert "handle_complaints" in rule_ids
        assert "share_positive_feedback" in rule_ids


# ============================================================================
# ConditionOperator enum tests
# ============================================================================


class TestConditionOperator:
    def test_all_operators_exist(self):
        expected = {
            "equals",
            "not_equals",
            "greater_than",
            "less_than",
            "greater_than_or_equal",
            "less_than_or_equal",
            "contains",
            "not_contains",
            "starts_with",
            "ends_with",
            "in",
            "not_in",
            "exists",
            "not_exists",
        }
        actual = {op.value for op in ConditionOperator}
        assert actual == expected


# ============================================================================
# BehaviorStrategy enum tests
# ============================================================================


class TestBehaviorStrategy:
    def test_all_strategies_exist(self):
        expected = {
            "llm_autonomous",
            "probabilistic",
            "rule_based",
            "scheduled",
            "mixed",
        }
        actual = {s.value for s in BehaviorStrategy}
        assert actual == expected
