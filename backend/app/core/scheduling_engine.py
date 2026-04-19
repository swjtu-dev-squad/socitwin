"""
Scheduling Engine - Timeline-based action scheduling for agents

This module implements scheduled action execution for agents based on
configured timelines, with support for repeating events and schedule looping.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
from collections import defaultdict

# OASIS framework imports
from oasis import SocialAgent, ManualAction, ActionType

# Local imports
from app.models.behavior import (
    BehaviorSchedule,
    TimelineEvent,
    BehaviorContext
)
from app.models.simulation import PlatformType, OASISActionType

logger = logging.getLogger(__name__)


class SchedulingEngineError(Exception):
    """Scheduling engine error base class"""
    pass


class ScheduleNotFoundError(SchedulingEngineError):
    """Schedule not found error"""
    pass


class InvalidScheduleError(SchedulingEngineError):
    """Invalid schedule configuration error"""
    pass


class SchedulingEngine:
    """
    Timeline-based scheduling engine

    Responsibilities:
    - Manage agent schedules and timeline events
    - Handle repeating events and schedule looping
    - Track execution state for each agent
    - Provide scheduled actions at appropriate steps
    """

    def __init__(self):
        """
        Initialize scheduling engine
        """
        # Agent schedules
        self._agent_schedules: Dict[int, BehaviorSchedule] = {}

        # Execution state tracking
        self._agent_execution_state: Dict[int, Dict[str, Any]] = defaultdict(dict)

        # Event cache for quick lookup
        self._event_cache: Dict[int, List[TimelineEvent]] = defaultdict(list)

        # Statistics
        self.schedule_execution_counts: Dict[int, int] = defaultdict(int)
        self.total_scheduled_actions = 0
        self.missed_events = 0

        logger.info("Scheduling Engine initialized")

    # ========================================================================
    # Public API
    # ========================================================================

    async def get_scheduled_action(
        self,
        agent_id: int,
        schedule: BehaviorSchedule,
        current_step: int
    ) -> Optional[ManualAction]:
        """
        Get scheduled action for an agent at current step

        Args:
            agent_id: Agent ID
            schedule: Behavior schedule
            current_step: Current simulation step

        Returns:
            ManualAction if scheduled event exists, None otherwise
        """
        try:
            # Ensure schedule is loaded for this agent
            if agent_id not in self._agent_schedules:
                await self.load_schedule(agent_id, schedule)

            # Get execution state for this agent
            execution_state = self._get_execution_state(agent_id)

            # Check if we should reset for looping schedule
            if schedule.loop:
                self._handle_schedule_looping(agent_id, schedule, execution_state, current_step)

            # Find events for current step
            events = self._find_events_for_step(agent_id, current_step, execution_state)

            if not events:
                # No events scheduled for this step
                return None

            # Select the first event (could be extended to handle multiple events)
            event = events[0]

            # Check if event should be executed
            if not self._should_execute_event(event, execution_state, current_step):
                return None

            # Update execution state
            self._update_event_execution(event, execution_state, current_step)

            # Create action from event
            action = self._create_action_from_event(event, agent_id, current_step)

            # Update statistics
            self._update_statistics(agent_id, event)

            logger.debug(
                f"Agent {agent_id} scheduled action '{event.action.value}' "
                f"at step {current_step}"
            )

            return action

        except Exception as e:
            logger.error(f"Failed to get scheduled action for agent {agent_id}: {e}")
            return None

    async def load_schedule(
        self,
        agent_id: int,
        schedule: BehaviorSchedule
    ) -> bool:
        """
        Load schedule for an agent

        Args:
            agent_id: Agent ID
            schedule: Behavior schedule

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate schedule
            self._validate_schedule(schedule)

            # Store schedule
            self._agent_schedules[agent_id] = schedule

            # Build event cache
            self._build_event_cache(agent_id, schedule)

            # Initialize execution state
            self._initialize_execution_state(agent_id, schedule)

            logger.info(f"Schedule '{schedule.name}' loaded for agent {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to load schedule for agent {agent_id}: {e}")
            return False

    async def unload_schedule(self, agent_id: int) -> bool:
        """
        Unload schedule for an agent

        Args:
            agent_id: Agent ID

        Returns:
            True if successful, False otherwise
        """
        try:
            if agent_id not in self._agent_schedules:
                logger.warning(f"No schedule loaded for agent {agent_id}")
                return False

            # Remove schedule and associated data
            del self._agent_schedules[agent_id]

            if agent_id in self._event_cache:
                del self._event_cache[agent_id]

            if agent_id in self._agent_execution_state:
                del self._agent_execution_state[agent_id]

            logger.info(f"Schedule unloaded for agent {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload schedule for agent {agent_id}: {e}")
            return False

    async def update_schedule(
        self,
        agent_id: int,
        schedule: BehaviorSchedule
    ) -> bool:
        """
        Update schedule for an agent

        Args:
            agent_id: Agent ID
            schedule: New schedule

        Returns:
            True if successful, False otherwise
        """
        try:
            # Unload existing schedule first
            await self.unload_schedule(agent_id)

            # Load new schedule
            return await self.load_schedule(agent_id, schedule)

        except Exception as e:
            logger.error(f"Failed to update schedule for agent {agent_id}: {e}")
            return False

    async def batch_get_scheduled_actions(
        self,
        agent_schedules: Dict[int, BehaviorSchedule],
        current_step: int
    ) -> Dict[int, Optional[ManualAction]]:
        """
        Get scheduled actions for multiple agents

        Args:
            agent_schedules: Dictionary mapping agent IDs to schedules
            current_step: Current simulation step

        Returns:
            Dictionary mapping agent IDs to actions (None if no scheduled event)
        """
        results = {}

        for agent_id, schedule in agent_schedules.items():
            action = await self.get_scheduled_action(agent_id, schedule, current_step)
            results[agent_id] = action

        return results

    def get_agent_schedule(self, agent_id: int) -> Optional[BehaviorSchedule]:
        """
        Get schedule for an agent

        Args:
            agent_id: Agent ID

        Returns:
            BehaviorSchedule or None if not found
        """
        return self._agent_schedules.get(agent_id)

    def get_schedule_progress(
        self,
        agent_id: int
    ) -> Dict[str, Any]:
        """
        Get progress information for an agent's schedule

        Args:
            agent_id: Agent ID

        Returns:
            Progress information dictionary
        """
        if agent_id not in self._agent_schedules:
            raise ScheduleNotFoundError(f"No schedule found for agent {agent_id}")

        schedule = self._agent_schedules[agent_id]
        execution_state = self._get_execution_state(agent_id)

        # Calculate progress
        total_events = len(schedule.timeline)
        executed_events = len(execution_state.get('executed_events', {}))
        upcoming_events = self._get_upcoming_events(agent_id, execution_state)

        # Calculate percentage if there are events
        if total_events > 0:
            progress_percent = (executed_events / total_events) * 100
        else:
            progress_percent = 0.0

        return {
            'agent_id': agent_id,
            'schedule_name': schedule.name,
            'total_events': total_events,
            'executed_events': executed_events,
            'upcoming_events': len(upcoming_events),
            'progress_percent': round(progress_percent, 2),
            'is_looping': schedule.loop,
            'current_cycle': execution_state.get('current_cycle', 1),
            'last_executed_step': execution_state.get('last_executed_step'),
            'next_scheduled_step': self._get_next_scheduled_step(agent_id, execution_state),
            'execution_counts': self.schedule_execution_counts.get(agent_id, 0),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get engine statistics

        Returns:
            Statistics dictionary
        """
        total_agents = len(self._agent_schedules)

        # Calculate schedule statistics
        schedule_stats = {}
        for agent_id, schedule in self._agent_schedules.items():
            progress = self.get_schedule_progress(agent_id)

            schedule_stats[agent_id] = {
                'schedule_name': schedule.name,
                'total_events': progress['total_events'],
                'executed_events': progress['executed_events'],
                'progress_percent': progress['progress_percent'],
                'execution_count': self.schedule_execution_counts.get(agent_id, 0),
                'is_looping': schedule.loop,
            }

        return {
            'total_agents': total_agents,
            'total_scheduled_actions': self.total_scheduled_actions,
            'missed_events': self.missed_events,
            'schedule_statistics': schedule_stats,
            'last_updated': datetime.now(),
        }

    def reset_statistics(self) -> None:
        """Reset engine statistics"""
        self.schedule_execution_counts.clear()
        self.total_scheduled_actions = 0
        self.missed_events = 0
        logger.info("Scheduling engine statistics reset")

    def reset_agent_state(self, agent_id: int) -> bool:
        """
        Reset execution state for an agent

        Args:
            agent_id: Agent ID

        Returns:
            True if successful, False otherwise
        """
        if agent_id not in self._agent_schedules:
            logger.warning(f"No schedule loaded for agent {agent_id}")
            return False

        schedule = self._agent_schedules[agent_id]
        self._initialize_execution_state(agent_id, schedule)

        logger.info(f"Execution state reset for agent {agent_id}")
        return True

    # ========================================================================
    # Schedule Execution Logic
    # ========================================================================

    def _find_events_for_step(
        self,
        agent_id: int,
        current_step: int,
        execution_state: Dict[str, Any]
    ) -> List[TimelineEvent]:
        """
        Find events scheduled for current step

        Args:
            agent_id: Agent ID
            current_step: Current simulation step
            execution_state: Agent execution state

        Returns:
            List of events for this step
        """
        events = []

        # Check cached events
        cached_events = self._event_cache.get(agent_id, [])

        for event in cached_events:
            # Calculate actual step considering repeats and cycles
            actual_step = self._calculate_actual_step(
                event, execution_state, current_step
            )

            if actual_step == current_step:
                events.append(event)

        return events

    def _calculate_actual_step(
        self,
        event: TimelineEvent,
        execution_state: Dict[str, Any],
        current_step: int
    ) -> int:
        """
        Calculate actual step for an event considering repeats and cycles

        Args:
            event: Timeline event
            execution_state: Agent execution state
            current_step: Current simulation step

        Returns:
            Actual step number or -1 if not applicable
        """
        base_step = event.step
        current_cycle = execution_state.get('current_cycle', 1)

        # Adjust for schedule looping
        if execution_state.get('schedule_looping', False):
            schedule_length = execution_state.get('schedule_length', 0)
            if schedule_length > 0:
                base_step = base_step + (schedule_length * (current_cycle - 1))

        # Check for repeating events
        if event.repeat_interval:
            # Get execution history for this event
            event_key = f"event_{event.step}"
            execution_history = execution_state.get('executed_events', {}).get(event_key, {})

            repeat_count = execution_history.get('repeat_count', 0)
            max_repeats = event.repeat_count

            # Check if we've exceeded repeat count
            if max_repeats and repeat_count >= max_repeats:
                return -1

            # Calculate step for next repeat
            repeat_step = base_step + (repeat_count * event.repeat_interval)

            # Check if this repeat matches current step
            if repeat_step == current_step:
                return repeat_step
            else:
                return -1

        # Non-repeating event
        return base_step

    def _should_execute_event(
        self,
        event: TimelineEvent,
        execution_state: Dict[str, Any],
        current_step: int
    ) -> bool:
        """
        Check if event should be executed

        Args:
            event: Timeline event
            execution_state: Agent execution state
            current_step: Current simulation step

        Returns:
            True if event should be executed
        """
        # Check if event has already been executed at this step
        event_key = f"event_{event.step}"
        executed_events = execution_state.get('executed_events', {})

        if event_key in executed_events:
            event_state = executed_events[event_key]

            # For non-repeating events, check if already executed
            if not event.repeat_interval:
                return False

            # For repeating events, check repeat count
            repeat_count = event_state.get('repeat_count', 0)
            if event.repeat_count and repeat_count >= event.repeat_count:
                return False

            # Check if this specific repeat has been executed
            last_executed_step = event_state.get('last_executed_step')
            if last_executed_step == current_step:
                return False

        return True

    def _update_event_execution(
        self,
        event: TimelineEvent,
        execution_state: Dict[str, Any],
        current_step: int
    ) -> None:
        """
        Update execution state for an event

        Args:
            event: Executed event
            execution_state: Agent execution state
            current_step: Current simulation step
        """
        event_key = f"event_{event.step}"

        # Initialize executed events dict if needed
        if 'executed_events' not in execution_state:
            execution_state['executed_events'] = {}

        # Get or create event state
        if event_key not in execution_state['executed_events']:
            execution_state['executed_events'][event_key] = {
                'event_step': event.step,
                'action': event.action.value,
                'repeat_count': 0,
                'last_executed_step': None,
                'first_executed_step': current_step,
            }

        event_state = execution_state['executed_events'][event_key]

        # Update execution details
        event_state['last_executed_step'] = current_step
        event_state['repeat_count'] = event_state.get('repeat_count', 0) + 1
        event_state['last_execution_time'] = datetime.now()

        # Update overall execution state
        execution_state['last_executed_step'] = current_step
        execution_state['last_execution_time'] = datetime.now()

    def _handle_schedule_looping(
        self,
        agent_id: int,
        schedule: BehaviorSchedule,
        execution_state: Dict[str, Any],
        current_step: int
    ) -> None:
        """
        Handle schedule looping logic

        Args:
            agent_id: Agent ID
            schedule: Behavior schedule
            execution_state: Agent execution state
            current_step: Current simulation step
        """
        if not schedule.loop:
            return

        # Calculate schedule length
        if not schedule.timeline:
            return

        max_step = max(event.step for event in schedule.timeline)
        schedule_length = max_step + 1  # Add 1 for zero-based steps

        # Store schedule length in execution state
        execution_state['schedule_length'] = schedule_length
        execution_state['schedule_looping'] = True

        # Check if we need to advance to next cycle
        current_cycle = execution_state.get('current_cycle', 1)
        cycle_end_step = schedule_length * current_cycle

        if current_step >= cycle_end_step:
            # Advance to next cycle
            execution_state['current_cycle'] = current_cycle + 1

            # Reset executed events for new cycle
            execution_state['executed_events'] = {}

            logger.debug(
                f"Agent {agent_id} schedule advanced to cycle {current_cycle + 1}"
            )

    # ========================================================================
    # Action Creation
    # ========================================================================

    def _create_action_from_event(
        self,
        event: TimelineEvent,
        agent_id: int,
        current_step: int
    ) -> ManualAction:
        """
        Create ManualAction from timeline event

        Args:
            event: Timeline event
            agent_id: Agent ID
            current_step: Current simulation step

        Returns:
            ManualAction
        """
        # Start with event's action arguments
        action_args = event.action_args.copy() if event.action_args else {}

        # Add context
        action_args['agent_id'] = agent_id
        action_args['step'] = current_step
        action_args['event_step'] = event.step
        action_args['event_description'] = event.description or ""

        # Add repeat information for repeating events
        if event.repeat_interval:
            action_args['repeat_interval'] = event.repeat_interval
            action_args['repeat_count'] = event.repeat_count

        # Map OASISActionType to ActionType
        try:
            oasis_action_type = getattr(ActionType, event.action.value)
        except AttributeError:
            logger.error(f"Action type {event.action.value} not found in OASIS ActionType")
            raise SchedulingEngineError(f"Invalid action type: {event.action.value}")

        # Create and return ManualAction
        return ManualAction(
            action_type=oasis_action_type,
            action_args=action_args
        )

    # ========================================================================
    # State Management
    # ========================================================================

    def _get_execution_state(self, agent_id: int) -> Dict[str, Any]:
        """
        Get execution state for an agent

        Args:
            agent_id: Agent ID

        Returns:
            Execution state dictionary
        """
        return self._agent_execution_state[agent_id]

    def _initialize_execution_state(
        self,
        agent_id: int,
        schedule: BehaviorSchedule
    ) -> None:
        """
        Initialize execution state for an agent

        Args:
            agent_id: Agent ID
            schedule: Behavior schedule
        """
        execution_state = {
            'agent_id': agent_id,
            'schedule_name': schedule.name,
            'current_cycle': 1,
            'executed_events': {},
            'last_executed_step': None,
            'last_execution_time': None,
            'schedule_looping': schedule.loop,
            'initialized_at': datetime.now(),
        }

        # Calculate schedule length for looping schedules
        if schedule.loop and schedule.timeline:
            max_step = max(event.step for event in schedule.timeline)
            execution_state['schedule_length'] = max_step + 1

        self._agent_execution_state[agent_id] = execution_state

    # ========================================================================
    # Event Cache Management
    # ========================================================================

    def _build_event_cache(
        self,
        agent_id: int,
        schedule: BehaviorSchedule
    ) -> None:
        """
        Build event cache for quick lookup

        Args:
            agent_id: Agent ID
            schedule: Behavior schedule
        """
        events = schedule.timeline.copy()

        # Sort events by step
        events.sort(key=lambda e: e.step)

        self._event_cache[agent_id] = events

    def _get_upcoming_events(
        self,
        agent_id: int,
        execution_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming events for an agent

        Args:
            agent_id: Agent ID
            execution_state: Agent execution state

        Returns:
            List of upcoming event information
        """
        upcoming = []

        cached_events = self._event_cache.get(agent_id, [])
        current_cycle = execution_state.get('current_cycle', 1)
        schedule_length = execution_state.get('schedule_length', 0)

        for event in cached_events:
            # Calculate base step considering current cycle
            base_step = event.step
            if schedule_length > 0 and execution_state.get('schedule_looping', False):
                base_step = base_step + (schedule_length * (current_cycle - 1))

            # Check if event has repeat intervals
            if event.repeat_interval:
                event_key = f"event_{event.step}"
                event_state = execution_state.get('executed_events', {}).get(event_key, {})
                repeat_count = event_state.get('repeat_count', 0)

                # Calculate next repeat step
                next_step = base_step + (repeat_count * event.repeat_interval)

                # Check if we've exceeded repeat count
                if event.repeat_count and repeat_count >= event.repeat_count:
                    continue

                upcoming.append({
                    'event_step': event.step,
                    'next_step': next_step,
                    'action': event.action.value,
                    'description': event.description,
                    'is_repeating': True,
                    'repeat_count': repeat_count + 1,
                    'max_repeats': event.repeat_count,
                })
            else:
                # Non-repeating event
                event_key = f"event_{event.step}"
                if event_key in execution_state.get('executed_events', {}):
                    # Already executed
                    continue

                upcoming.append({
                    'event_step': event.step,
                    'next_step': base_step,
                    'action': event.action.value,
                    'description': event.description,
                    'is_repeating': False,
                })

        # Sort by next step
        upcoming.sort(key=lambda e: e['next_step'])

        return upcoming

    def _get_next_scheduled_step(
        self,
        agent_id: int,
        execution_state: Dict[str, Any]
    ) -> Optional[int]:
        """
        Get next scheduled step for an agent

        Args:
            agent_id: Agent ID
            execution_state: Agent execution state

        Returns:
            Next scheduled step or None
        """
        upcoming = self._get_upcoming_events(agent_id, execution_state)
        if upcoming:
            return upcoming[0]['next_step']
        return None

    # ========================================================================
    # Validation
    # ========================================================================

    def _validate_schedule(self, schedule: BehaviorSchedule) -> None:
        """
        Validate schedule configuration

        Args:
            schedule: Schedule to validate

        Raises:
            InvalidScheduleError: If validation fails
        """
        if not schedule.name or not isinstance(schedule.name, str):
            raise InvalidScheduleError("Schedule must have a non-empty string name")

        if not isinstance(schedule.timeline, list):
            raise InvalidScheduleError("Schedule timeline must be a list")

        # Validate each event
        seen_steps = set()

        for event in schedule.timeline:
            self._validate_timeline_event(event)

            # Check for duplicate steps (non-repeating events only)
            if not event.repeat_interval and event.step in seen_steps:
                logger.warning(
                    f"Duplicate step {event.step} in schedule '{schedule.name}'"
                )
            seen_steps.add(event.step)

    def _validate_timeline_event(self, event: TimelineEvent) -> None:
        """
        Validate timeline event

        Args:
            event: Timeline event

        Raises:
            InvalidScheduleError: If validation fails
        """
        if event.step < 0:
            raise InvalidScheduleError(f"Event step must be >= 0, got {event.step}")

        try:
            # Validate action type
            OASISActionType(event.action.value)
        except ValueError:
            raise InvalidScheduleError(f"Invalid action type: {event.action}")

        # Validate repeat configuration
        if event.repeat_interval is not None:
            if event.repeat_interval < 1:
                raise InvalidScheduleError(
                    f"Repeat interval must be >= 1, got {event.repeat_interval}"
                )

            if event.repeat_count is not None and event.repeat_count < 1:
                raise InvalidScheduleError(
                    f"Repeat count must be >= 1, got {event.repeat_count}"
                )

    # ========================================================================
    # Statistics
    # ========================================================================

    def _update_statistics(self, agent_id: int, event: TimelineEvent) -> None:
        """
        Update engine statistics

        Args:
            agent_id: Agent ID
            event: Executed event
        """
        self.schedule_execution_counts[agent_id] = (
            self.schedule_execution_counts.get(agent_id, 0) + 1
        )
        self.total_scheduled_actions += 1

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_loaded_agents(self) -> List[int]:
        """Get list of agent IDs with loaded schedules"""
        return list(self._agent_schedules.keys())

    def clear_all_schedules(self) -> None:
        """Clear all schedules from engine"""
        self._agent_schedules.clear()
        self._event_cache.clear()
        self._agent_execution_state.clear()

        logger.info("All schedules cleared from engine")


# ============================================================================
# Factory Function
# ============================================================================

_scheduling_engine = None


def get_scheduling_engine() -> SchedulingEngine:
    """
    Get scheduling engine instance (singleton)

    Returns:
        SchedulingEngine instance
    """
    global _scheduling_engine

    if _scheduling_engine is None:
        _scheduling_engine = SchedulingEngine()
        logger.info("Scheduling Engine singleton created")

    return _scheduling_engine


def reset_scheduling_engine() -> None:
    """Reset scheduling engine singleton (mainly for testing)"""
    global _scheduling_engine
    _scheduling_engine = None
    logger.info("Scheduling Engine singleton reset")