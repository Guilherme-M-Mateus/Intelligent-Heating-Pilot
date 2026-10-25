"""Tests for ControlPreheatingUseCase.

Tests verify that the use case correctly delegates to ISchedulerCommander
and tracks preheating state.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.intelligent_heating_pilot.application.use_cases import (
    ControlPreheatingUseCase,
)


class TestControlPreheatingUseCase:
    """Test suite for ControlPreheatingUseCase.

    Verifies delegation to ISchedulerCommander and internal state tracking.
    """

    @pytest.fixture
    def mock_scheduler_commander(self) -> Mock:
        """Create mock ISchedulerCommander."""
        commander = Mock()
        commander.run_action = AsyncMock()
        commander.cancel_action = AsyncMock()
        return commander

    @pytest.fixture
    def use_case(self, mock_scheduler_commander: Mock) -> ControlPreheatingUseCase:
        """Create ControlPreheatingUseCase instance."""
        return ControlPreheatingUseCase(mock_scheduler_commander)

    @pytest.mark.asyncio
    async def test_cancel_preheating_delegates_to_commander(
        self,
        use_case: ControlPreheatingUseCase,
        mock_scheduler_commander: Mock,
    ) -> None:
        """Test that cancel_preheating() delegates to scheduler commander.

        Verifies delegation pattern when preheating is active.
        """
        # GIVEN: Preheating is active
        target_time = datetime(2025, 2, 10, 11, 0, 0)
        scheduler_entity_id = "schedule.heating"
        await use_case.start_preheating(
            target_time=target_time,
            target_temp=21.0,
            scheduler_entity_id=scheduler_entity_id,
        )

        # WHEN: cancel_preheating is called
        await use_case.cancel_preheating(scheduler_entity_id)

        # THEN: Commander cancel_action is called
        mock_scheduler_commander.cancel_action.assert_called_once_with(scheduler_entity_id)

    @pytest.mark.asyncio
    async def test_start_preheating_delegates_to_commander(
        self,
        use_case: ControlPreheatingUseCase,
        mock_scheduler_commander: Mock,
    ) -> None:
        """Test that start_preheating() delegates to scheduler commander.

        Verifies delegation with parameters.
        """
        # GIVEN: Parameters for starting preheating
        target_time = datetime(2025, 2, 10, 11, 0, 0)
        target_temp = 21.0
        scheduler_entity_id = "schedule.heating"

        # WHEN: start_preheating is called
        await use_case.start_preheating(
            target_time=target_time,
            target_temp=target_temp,
            scheduler_entity_id=scheduler_entity_id,
        )

        # THEN: Commander run_action is called with correct parameters
        mock_scheduler_commander.run_action.assert_called_once_with(
            target_time, scheduler_entity_id
        )

    def test_is_preheating_active_returns_state(
        self,
        use_case: ControlPreheatingUseCase,
    ) -> None:
        """Test that is_preheating_active() returns internal state.

        Verifies state tracking.
        """
        # GIVEN: No preheating started
        # WHEN: is_preheating_active is called
        result = use_case.is_preheating_active()

        # THEN: Result is False
        assert result is False

    @pytest.mark.asyncio
    async def test_is_preheating_active_after_start(
        self,
        use_case: ControlPreheatingUseCase,
        mock_scheduler_commander: Mock,
    ) -> None:
        """Test that is_preheating_active() returns True after start."""
        # GIVEN: Preheating has been started
        await use_case.start_preheating(
            target_time=datetime(2025, 2, 10, 11, 0, 0),
            target_temp=21.0,
            scheduler_entity_id="schedule.heating",
        )

        # WHEN/THEN
        assert use_case.is_preheating_active() is True

    def test_get_preheating_target_time_returns_state(
        self,
        use_case: ControlPreheatingUseCase,
    ) -> None:
        """Test that get_preheating_target_time() returns internal state.

        Verifies state tracking.
        """
        # GIVEN: No preheating started
        # WHEN: get_preheating_target_time is called
        result = use_case.get_preheating_target_time()

        # THEN: Result is None
        assert result is None

    @pytest.mark.asyncio
    async def test_get_preheating_target_time_after_start(
        self,
        use_case: ControlPreheatingUseCase,
        mock_scheduler_commander: Mock,
    ) -> None:
        """Test that get_preheating_target_time() returns time after start."""
        # GIVEN: Preheating has been started
        target_time = datetime(2025, 2, 10, 11, 0, 0)
        await use_case.start_preheating(
            target_time=target_time,
            target_temp=21.0,
            scheduler_entity_id="schedule.heating",
        )

        # WHEN/THEN
        assert use_case.get_preheating_target_time() == target_time

    def test_restart_suppression_is_scoped_to_its_slot(
        self,
        use_case: ControlPreheatingUseCase,
    ) -> None:
        """Suppression for one slot must not block anticipation of the next one."""
        suppressed_target = datetime(2025, 2, 10, 7, 0, 0)
        next_target = datetime(2025, 2, 10, 18, 0, 0)

        use_case.suppress_restart(suppressed_target, 21.0)

        assert use_case.is_restart_suppressed(suppressed_target, 21.0)
        assert not use_case.is_restart_suppressed(next_target, 21.0)

    def test_raising_slot_target_lifts_restart_suppression(
        self,
        use_case: ControlPreheatingUseCase,
    ) -> None:
        """A new target temperature is a new request, so the slot may heat again."""
        target_time = datetime(2025, 2, 10, 7, 0, 0)

        use_case.suppress_restart(target_time, 21.0)

        assert not use_case.is_restart_suppressed(target_time, 23.0)

    @pytest.mark.asyncio
    async def test_start_preheating_is_refused_for_suppressed_slot(
        self,
        use_case: ControlPreheatingUseCase,
        mock_scheduler_commander: Mock,
    ) -> None:
        """Every start path honours the suppression, not only the recalculation one."""
        target_time = datetime(2025, 2, 10, 7, 0, 0)
        use_case.suppress_restart(target_time, 21.0)

        started = await use_case.start_preheating(
            target_time=target_time,
            target_temp=21.0,
            scheduler_entity_id="schedule.heating",
        )

        assert not started
        assert not use_case.is_preheating_active()
        mock_scheduler_commander.run_action.assert_not_called()
