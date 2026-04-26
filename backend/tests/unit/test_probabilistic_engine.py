"""
Tests for the ProbabilisticEngine - action selection based on probability distributions.
"""

from unittest.mock import MagicMock

import pytest

from app.models.behavior import (
    ActionProbability,
    BehaviorContext,
    ProbabilityDistribution,
)
from app.models.simulation import OASISActionType, PlatformType

# ============================================================================
# Mock helpers
# ============================================================================


def make_mock_agent(
    agent_id=0, user_name="test_user", name="Test User", description="A test agent"
):
    agent = MagicMock()
    agent.social_agent_id = agent_id
    agent.user_info.user_name = user_name
    agent.user_info.name = name
    agent.user_info.description = description
    return agent


def make_mock_context(current_step=0, platform=PlatformType.TWITTER, agent_id=0):
    return BehaviorContext(
        current_step=current_step,
        platform=platform,
        agent_id=agent_id,
    )


# ============================================================================
# ProbabilisticEngine tests
# ============================================================================


class TestProbabilisticEngineInit:
    def test_init_with_twitter_platform(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        assert engine.platform == PlatformType.TWITTER
        actions = engine.get_available_action_types()
        assert "CREATE_POST" in actions
        assert "LIKE_POST" in actions

    def test_init_with_reddit_platform(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.REDDIT)
        actions = engine.get_available_action_types()
        assert "DISLIKE_POST" in actions

    def test_init_with_unknown_platform(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.REDDIT)
        assert engine.get_available_action_types()


class TestProbabilisticEngineActionSelection:
    @pytest.mark.asyncio
    async def test_select_action_returns_manual_action(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)

        dist = ProbabilityDistribution(
            name="test",
            actions=[
                ActionProbability(action_type=OASISActionType.CREATE_POST, probability=1.0),
            ],
        )

        agent = make_mock_agent()
        context = make_mock_context(current_step=1)

        action = await engine.select_action(agent, dist, context)
        assert action is not None
        assert action.action_args is not None
        assert "agent_id" in action.action_args

    @pytest.mark.asyncio
    async def test_select_action_with_multiple_probabilities(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)

        dist = ProbabilityDistribution(
            name="test",
            actions=[
                ActionProbability(action_type=OASISActionType.CREATE_POST, probability=0.5),
                ActionProbability(action_type=OASISActionType.LIKE_POST, probability=0.5),
            ],
        )

        agent = make_mock_agent()
        context = make_mock_context(current_step=1)

        action = await engine.select_action(agent, dist, context)
        assert action is not None

    @pytest.mark.asyncio
    async def test_select_action_with_conditions(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)

        dist = ProbabilityDistribution(
            name="test",
            actions=[
                ActionProbability(
                    action_type=OASISActionType.CREATE_POST,
                    probability=0.5,
                    conditions={"platform": "nonexistent"},
                ),
                ActionProbability(
                    action_type=OASISActionType.LIKE_POST,
                    probability=0.5,
                ),
            ],
        )

        agent = make_mock_agent()
        context = make_mock_context(current_step=1)

        # The condition won't match, so only LIKE_POST should be available
        action = await engine.select_action(agent, dist, context)
        assert action is not None

    @pytest.mark.asyncio
    async def test_select_action_statistics_update(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)

        dist = ProbabilityDistribution(
            name="test",
            actions=[
                ActionProbability(action_type=OASISActionType.CREATE_POST, probability=1.0),
            ],
        )

        agent = make_mock_agent()
        context = make_mock_context(current_step=1)

        await engine.select_action(agent, dist, context)
        stats = engine.get_statistics()
        assert stats["total_selections"] >= 1


class TestProbabilisticEngineNormalization:
    def test_normalize_probabilities(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)

        weighted = [
            (OASISActionType.CREATE_POST, 2.0),
            (OASISActionType.LIKE_POST, 2.0),
        ]
        normalized = engine._normalize_probabilities(weighted)
        total = sum(p for _, p in normalized)
        assert abs(total - 1.0) < 0.01

    def test_normalize_zero_sum(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)

        weighted = [
            (OASISActionType.CREATE_POST, 0.0),
            (OASISActionType.LIKE_POST, 0.0),
        ]
        normalized = engine._normalize_probabilities(weighted)
        total = sum(p for _, p in normalized)
        assert abs(total - 1.0) < 0.01

    def test_normalize_empty_list(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        result = engine._normalize_probabilities([])
        assert result == []


class TestProbabilisticEngineConditionChecking:
    def test_check_conditions_matching(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        context = make_mock_context(current_step=5)
        result = engine._check_conditions({"current_step": 5}, context)
        assert result is True

    def test_check_conditions_non_matching(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        context = make_mock_context(current_step=5)
        result = engine._check_conditions({"current_step": 999}, context)
        assert result is False

    def test_check_conditions_none(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        context = make_mock_context()
        result = engine._check_conditions(None, context)
        assert result is True

    def test_check_conditions_empty_dict(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        context = make_mock_context()
        result = engine._check_conditions({}, context)
        assert result is True

    def test_check_conditions_nonexistent_field(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        context = make_mock_context()
        result = engine._check_conditions({"nonexistent_field": 123}, context)
        assert result is False


class TestProbabilisticEngineStatistics:
    def test_get_statistics(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        stats = engine.get_statistics()
        assert stats["total_selections"] == 0
        assert stats["platform"] == "twitter"
        assert "action_counts" in stats
        assert "percentages" in stats

    def test_reset_statistics(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        engine.total_selections = 100
        engine.action_selection_counts = {"CREATE_POST": 50}
        engine.reset_statistics()
        assert engine.total_selections == 0
        assert engine.action_selection_counts == {}


class TestProbabilisticEngineFactory:
    def test_get_probabilistic_engine(self):
        from app.core.probabilistic_engine import (
            get_probabilistic_engine,
            reset_probabilistic_engines,
        )

        reset_probabilistic_engines()
        engine = get_probabilistic_engine(PlatformType.TWITTER)
        assert engine.platform == PlatformType.TWITTER

    def test_singleton_per_platform(self):
        from app.core.probabilistic_engine import (
            get_probabilistic_engine,
            reset_probabilistic_engines,
        )

        reset_probabilistic_engines()
        engine1 = get_probabilistic_engine(PlatformType.TWITTER)
        engine2 = get_probabilistic_engine(PlatformType.TWITTER)
        assert engine1 is engine2

        engine3 = get_probabilistic_engine(PlatformType.REDDIT)
        assert engine1 is not engine3


class TestProbabilisticEngineActionAvailability:
    def test_create_post_always_available(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        agent = make_mock_agent()
        context = make_mock_context(current_step=0)
        result = engine._is_action_available(OASISActionType.CREATE_POST, agent, context)
        assert result is True

    def test_like_post_needs_step_above_zero(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        agent = make_mock_agent()
        context0 = make_mock_context(current_step=0)
        context1 = make_mock_context(current_step=1)
        assert engine._is_action_available(OASISActionType.LIKE_POST, agent, context0) is False
        assert engine._is_action_available(OASISActionType.LIKE_POST, agent, context1) is True

    def test_do_nothing_always_available(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        agent = make_mock_agent()
        context = make_mock_context(current_step=0)
        result = engine._is_action_available(OASISActionType.DO_NOTHING, agent, context)
        assert result is True

    def test_refresh_always_available(self):
        from app.core.probabilistic_engine import ProbabilisticEngine

        engine = ProbabilisticEngine(PlatformType.TWITTER)
        agent = make_mock_agent()
        context = make_mock_context(current_step=0)
        result = engine._is_action_available(OASISActionType.REFRESH, agent, context)
        assert result is True
