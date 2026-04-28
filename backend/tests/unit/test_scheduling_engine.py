"""
Tests for the SchedulingEngine - timeline-based action scheduling.
"""

from unittest.mock import MagicMock

import pytest

from app.models.behavior import (
    BehaviorSchedule,
    TimelineEvent,
)
from app.models.simulation import OASISActionType

# ============================================================================
# SchedulingEngine initialization tests
# ============================================================================


class TestSchedulingEngineInit:
    def test_initialization(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        assert engine.total_scheduled_actions == 0
        assert engine.missed_events == 0
        assert engine.get_loaded_agents() == []

    def test_singleton_factory(self):
        from app.core.scheduling_engine import (
            get_scheduling_engine,
            reset_scheduling_engine,
        )

        reset_scheduling_engine()
        e1 = get_scheduling_engine()
        e2 = get_scheduling_engine()
        assert e1 is e2
        reset_scheduling_engine()
        e3 = get_scheduling_engine()
        assert e1 is not e3


# ============================================================================
# SchedulingEngine load/unload tests
# ============================================================================


class TestScheduleLoading:
    @pytest.mark.asyncio
    async def test_load_schedule(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="test",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        result = await engine.load_schedule(0, schedule)
        assert result is True
        assert 0 in engine.get_loaded_agents()

    @pytest.mark.asyncio
    async def test_load_schedule_with_loop(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="loop_test",
            timeline=[
                TimelineEvent(step=0, action=OASISActionType.CREATE_POST),
                TimelineEvent(step=5, action=OASISActionType.LIKE_POST),
            ],
            loop=True,
        )
        result = await engine.load_schedule(1, schedule)
        assert result is True

    @pytest.mark.asyncio
    async def test_unload_schedule(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="test",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        await engine.load_schedule(0, schedule)
        result = await engine.unload_schedule(0)
        assert result is True
        assert 0 not in engine.get_loaded_agents()

    @pytest.mark.asyncio
    async def test_unload_nonexistent_schedule(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        result = await engine.unload_schedule(999)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_schedule(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule1 = BehaviorSchedule(
            name="v1",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        schedule2 = BehaviorSchedule(
            name="v2",
            timeline=[TimelineEvent(step=10, action=OASISActionType.LIKE_POST)],
        )
        await engine.load_schedule(0, schedule1)
        result = await engine.update_schedule(0, schedule2)
        assert result is True
        assert engine.get_agent_schedule(0).name == "v2"


# ============================================================================
# SchedulingEngine action retrieval tests
# ============================================================================


class TestScheduledActionRetrieval:
    @pytest.mark.asyncio
    async def test_get_action_at_exact_step(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="test",
            timeline=[
                TimelineEvent(step=5, action=OASISActionType.CREATE_POST),
            ],
        )
        await engine.load_schedule(0, schedule)

        action = await engine.get_scheduled_action(0, schedule, current_step=5)
        assert action is not None

    @pytest.mark.asyncio
    async def test_no_action_at_different_step(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="test",
            timeline=[TimelineEvent(step=5, action=OASISActionType.CREATE_POST)],
        )
        await engine.load_schedule(0, schedule)

        action = await engine.get_scheduled_action(0, schedule, current_step=3)
        assert action is None

    @pytest.mark.asyncio
    async def test_action_includes_context(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="test",
            timeline=[
                TimelineEvent(
                    step=2,
                    action=OASISActionType.CREATE_COMMENT,
                    action_args={"content": "Hello!"},
                    description="Test event",
                ),
            ],
        )
        await engine.load_schedule(0, schedule)

        action = await engine.get_scheduled_action(0, schedule, current_step=2)
        assert action is not None
        assert action.action_args["agent_id"] == 0
        assert action.action_args["step"] == 2
        assert action.action_args["content"] == "Hello!"
        assert action.action_args["event_description"] == "Test event"

    @pytest.mark.asyncio
    async def test_empty_timeline(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(name="empty", timeline=[])
        await engine.load_schedule(0, schedule)

        action = await engine.get_scheduled_action(0, schedule, current_step=0)
        assert action is None

    @pytest.mark.asyncio
    async def test_multiple_events_same_step_returns_first(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="test",
            timeline=[
                TimelineEvent(step=1, action=OASISActionType.LIKE_POST),
                TimelineEvent(step=1, action=OASISActionType.CREATE_POST),
            ],
        )
        await engine.load_schedule(0, schedule)

        action = await engine.get_scheduled_action(0, schedule, current_step=1)
        assert action is not None


# ============================================================================
# SchedulingEngine repeat tests
# ============================================================================


class TestRepeatingEvents:
    @pytest.mark.asyncio
    async def test_repeating_event(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="repeat_test",
            timeline=[
                TimelineEvent(
                    step=0,
                    action=OASISActionType.LIKE_POST,
                    repeat_interval=2,
                    repeat_count=5,
                ),
            ],
        )
        await engine.load_schedule(0, schedule)

        # Step 0: first occurrence
        action = await engine.get_scheduled_action(0, schedule, current_step=0)
        assert action is not None

        # Step 1: no event
        action = await engine.get_scheduled_action(0, schedule, current_step=1)
        assert action is None

        # Step 2: repeat (0 + 1*2)
        action = await engine.get_scheduled_action(0, schedule, current_step=2)
        assert action is not None

        # Step 4: repeat (0 + 2*2)
        action = await engine.get_scheduled_action(0, schedule, current_step=4)
        assert action is not None

    @pytest.mark.asyncio
    async def test_non_repeating_event_only_executes_once(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="once",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        await engine.load_schedule(0, schedule)

        action1 = await engine.get_scheduled_action(0, schedule, current_step=0)
        assert action1 is not None

        action2 = await engine.get_scheduled_action(0, schedule, current_step=0)
        assert action2 is None  # Already executed


# ============================================================================
# SchedulingEngine looping tests
# ============================================================================


class TestScheduleLooping:
    @pytest.mark.asyncio
    async def test_looping_schedule_cycles(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="looping",
            timeline=[
                TimelineEvent(step=0, action=OASISActionType.CREATE_POST),
                TimelineEvent(step=2, action=OASISActionType.LIKE_POST),
            ],
            loop=True,
        )
        await engine.load_schedule(0, schedule)

        # First cycle
        action0 = await engine.get_scheduled_action(0, schedule, current_step=0)
        assert action0 is not None

        action2 = await engine.get_scheduled_action(0, schedule, current_step=2)
        assert action2 is not None

        # Second cycle: schedule length is 3 (max_step=2 + 1)
        # Step 3 = step 0 of second cycle
        action3 = await engine.get_scheduled_action(0, schedule, current_step=3)
        assert action3 is not None

        # Step 5 = step 2 of second cycle
        action5 = await engine.get_scheduled_action(0, schedule, current_step=5)
        assert action5 is not None


# ============================================================================
# SchedulingEngine schedule progress tests
# ============================================================================


class TestScheduleProgress:
    @pytest.mark.asyncio
    async def test_get_schedule_progress(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="progress_test",
            timeline=[
                TimelineEvent(step=0, action=OASISActionType.CREATE_POST),
                TimelineEvent(step=5, action=OASISActionType.LIKE_POST),
                TimelineEvent(step=10, action=OASISActionType.CREATE_COMMENT),
            ],
        )
        await engine.load_schedule(0, schedule)

        # Execute first event
        await engine.get_scheduled_action(0, schedule, current_step=0)

        progress = engine.get_schedule_progress(0)
        assert progress["total_events"] == 3
        assert progress["executed_events"] == 1
        assert progress["schedule_name"] == "progress_test"

    @pytest.mark.asyncio
    async def test_get_schedule_progress_nonexistent_agent(self):
        from app.core.scheduling_engine import ScheduleNotFoundError, SchedulingEngine

        engine = SchedulingEngine()
        with pytest.raises(ScheduleNotFoundError):
            engine.get_schedule_progress(999)


# ============================================================================
# SchedulingEngine validation tests
# ============================================================================


class TestScheduleValidation:
    def test_valid_schedule_passes(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        schedule = BehaviorSchedule(
            name="valid",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        engine._validate_schedule(schedule)  # Should not raise

    def test_empty_name_raises(self):
        from app.core.scheduling_engine import InvalidScheduleError, SchedulingEngine

        engine = SchedulingEngine()
        with pytest.raises(InvalidScheduleError):
            engine._validate_schedule(BehaviorSchedule(name="", timeline=[]))

    def test_negative_step_raises(self):
        from app.core.scheduling_engine import InvalidScheduleError, SchedulingEngine

        engine = SchedulingEngine()
        event = TimelineEvent(step=0, action=OASISActionType.CREATE_POST)
        event.step = -1
        with pytest.raises(InvalidScheduleError):
            engine._validate_timeline_event(event)

    def test_invalid_action_type_raises(self):
        from app.core.scheduling_engine import InvalidScheduleError, SchedulingEngine

        engine = SchedulingEngine()
        event = TimelineEvent(step=0, action=OASISActionType.CREATE_POST)
        event.action = MagicMock()
        event.action.value = "INVALID_ACTION"
        with pytest.raises(InvalidScheduleError):
            engine._validate_timeline_event(event)

    def test_zero_repeat_interval_raises(self):
        from app.core.scheduling_engine import InvalidScheduleError, SchedulingEngine

        engine = SchedulingEngine()
        event = TimelineEvent(step=0, action=OASISActionType.CREATE_POST, repeat_interval=2)
        event.repeat_interval = 0
        with pytest.raises(InvalidScheduleError):
            engine._validate_timeline_event(event)

    def test_zero_repeat_count_raises(self):
        from app.core.scheduling_engine import InvalidScheduleError, SchedulingEngine

        engine = SchedulingEngine()
        event = TimelineEvent(
            step=0, action=OASISActionType.CREATE_POST, repeat_interval=1, repeat_count=2
        )
        event.repeat_count = 0
        with pytest.raises(InvalidScheduleError):
            engine._validate_timeline_event(event)


# ============================================================================
# SchedulingEngine statistics tests
# ============================================================================


class TestSchedulingEngineStatistics:
    def test_get_statistics_empty(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        stats = engine.get_statistics()
        assert stats["total_agents"] == 0
        assert stats["total_scheduled_actions"] == 0
        assert stats["missed_events"] == 0

    @pytest.mark.asyncio
    async def test_get_statistics_with_data(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="stats_test",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        await engine.load_schedule(0, schedule)
        await engine.get_scheduled_action(0, schedule, current_step=0)

        stats = engine.get_statistics()
        assert stats["total_agents"] == 1
        assert stats["total_scheduled_actions"] == 1

    def test_reset_statistics(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        engine.total_scheduled_actions = 100
        engine.missed_events = 5
        engine.reset_statistics()
        assert engine.total_scheduled_actions == 0
        assert engine.missed_events == 0

    def test_clear_all_schedules(self):
        import asyncio

        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        schedule = BehaviorSchedule(
            name="test",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        asyncio.run(engine.load_schedule(0, schedule))
        assert len(engine.get_loaded_agents()) == 1
        engine.clear_all_schedules()
        assert len(engine.get_loaded_agents()) == 0


# ============================================================================
# SchedulingEngine state management tests
# ============================================================================


class TestStateManagement:
    @pytest.mark.asyncio
    async def test_reset_agent_state(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()

        schedule = BehaviorSchedule(
            name="reset_test",
            timeline=[TimelineEvent(step=0, action=OASISActionType.CREATE_POST)],
        )
        await engine.load_schedule(0, schedule)
        await engine.get_scheduled_action(0, schedule, current_step=0)

        # After execution, event should be marked as executed
        progress = engine.get_schedule_progress(0)
        assert progress["executed_events"] > 0

        # Reset should clear execution state
        result = engine.reset_agent_state(0)
        assert result is True
        progress_after = engine.get_schedule_progress(0)
        assert progress_after["executed_events"] == 0

    @pytest.mark.asyncio
    async def test_reset_nonexistent_agent(self):
        from app.core.scheduling_engine import SchedulingEngine

        engine = SchedulingEngine()
        result = engine.reset_agent_state(999)
        assert result is False
