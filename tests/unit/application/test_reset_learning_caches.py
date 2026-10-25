"""Regression tests for issue #181: reset_learning must clear in-memory caches.

Before the fix, reset_learning only cleared storage. The lifecycle managers and
HeatingApplication kept serving the old learned values from memory, so the
reset had no visible effect until Home Assistant was restarted.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.intelligent_heating_pilot.application.heating_cycle_lifecycle_manager import (
    HeatingCycleLifecycleManager,
)
from custom_components.intelligent_heating_pilot.application.lhs_lifecycle_manager import (
    LhsLifecycleManager,
)
from custom_components.intelligent_heating_pilot.const import EVENT_DEAD_TIME_UPDATED
from custom_components.intelligent_heating_pilot.domain.constants import (
    DEFAULT_LEARNED_SLOPE,
)
from custom_components.intelligent_heating_pilot.domain.interfaces.device_config_reader_interface import (
    DeviceConfig,
)
from custom_components.intelligent_heating_pilot.heating_application import (
    HeatingApplication,
)

DEVICE_ID = "climate.test_vtherm"
STALE_GLOBAL_LHS = 3.5
STALE_CONTEXTUAL_LHS = 4.2
STALE_DEAD_TIME = 7.0


@pytest.fixture
def empty_model_storage() -> Mock:
    """Create an ILhsStorage mock whose content was just cleared."""
    storage = Mock()
    storage.get_cached_global_lhs = AsyncMock(return_value=None)
    storage.get_cached_contextual_lhs = AsyncMock(return_value=None)
    return storage


@pytest.fixture
def lhs_manager(empty_model_storage: Mock) -> LhsLifecycleManager:
    """Create an LhsLifecycleManager holding stale values in memory."""
    manager = LhsLifecycleManager(
        model_storage=empty_model_storage,
        global_lhs_calculator=Mock(),
        contextual_lhs_calculator=Mock(),
        timer_scheduler=None,
    )
    manager._cached_global_lhs = STALE_GLOBAL_LHS
    manager._cached_contextual_lhs = {6: STALE_CONTEXTUAL_LHS}
    return manager


class TestLhsLifecycleManagerInvalidateMemoryCache:
    """invalidate_memory_cache() must make reads fall through to storage."""

    @pytest.mark.asyncio
    async def test_global_lhs_falls_back_to_default_after_invalidation(
        self, lhs_manager: LhsLifecycleManager, empty_model_storage: Mock
    ) -> None:
        """After invalidation, an empty storage yields the default LHS, not the stale one."""
        lhs_manager.invalidate_memory_cache()

        result = await lhs_manager.get_global_lhs()

        assert result == DEFAULT_LEARNED_SLOPE
        empty_model_storage.get_cached_global_lhs.assert_awaited_once()

    def test_contextual_cache_is_emptied(self, lhs_manager: LhsLifecycleManager) -> None:
        """Contextual LHS values held in memory are dropped."""
        lhs_manager.invalidate_memory_cache()

        assert lhs_manager._cached_global_lhs is None
        assert lhs_manager._cached_contextual_lhs == {}


class TestHeatingCycleLifecycleManagerInvalidateMemoryCache:
    """invalidate_memory_cache() must drop every cached cycle list."""

    def test_cycles_cache_is_emptied(
        self, heating_cycle_manager_minimal: HeatingCycleLifecycleManager
    ) -> None:
        """Cached cycles would otherwise keep feeding dead-time learning."""
        cache_key = (DEVICE_ID, datetime(2025, 2, 10).date())
        heating_cycle_manager_minimal._cached_cycles_for_target_time[cache_key] = [Mock()]

        heating_cycle_manager_minimal.invalidate_memory_cache()

        assert heating_cycle_manager_minimal._cached_cycles_for_target_time == {}


@pytest.fixture
def app_with_stale_caches() -> HeatingApplication:
    """Create a HeatingApplication whose sensor caches hold stale learned values."""
    device_config = DeviceConfig(
        device_id=DEVICE_ID,
        vtherm_entity_id=DEVICE_ID,
        scheduler_entities=["schedule.heating"],
        lhs_retention_days=30,
    )
    app = HeatingApplication(Mock(), device_config)
    app._orchestrator = Mock()
    app._orchestrator.reset_all_learning_data = AsyncMock()
    app._event_bridge = Mock()
    app._lhs_cache = STALE_GLOBAL_LHS
    app._contextual_lhs_cache = {6: STALE_CONTEXTUAL_LHS}
    app._last_known_dead_time = STALE_DEAD_TIME
    return app


class TestHeatingApplicationResetLearning:
    """async_reset_learning() must refresh everything derived from learned data."""

    @pytest.mark.asyncio
    async def test_delegates_reset_to_orchestrator(
        self, app_with_stale_caches: HeatingApplication
    ) -> None:
        """Storage and lifecycle caches are reset through the orchestrator."""
        await app_with_stale_caches.async_reset_learning()

        app_with_stale_caches._orchestrator.reset_all_learning_data.assert_awaited_once_with(
            device_id=DEVICE_ID
        )

    @pytest.mark.asyncio
    async def test_sensor_caches_are_reset(self, app_with_stale_caches: HeatingApplication) -> None:
        """Sensors read the default LHS everywhere, including hours that had a contextual value."""
        await app_with_stale_caches.async_reset_learning()

        assert app_with_stale_caches.get_learned_heating_slope() == DEFAULT_LEARNED_SLOPE
        assert app_with_stale_caches.get_contextual_learned_heating_slope(6) == (
            DEFAULT_LEARNED_SLOPE
        )
        assert app_with_stale_caches._last_known_dead_time is None

    @pytest.mark.asyncio
    async def test_dead_time_event_fired_and_recalculation_requested(
        self, app_with_stale_caches: HeatingApplication
    ) -> None:
        """The Dead Time sensor refreshes and anticipation is recalculated."""
        await app_with_stale_caches.async_reset_learning()

        app_with_stale_caches.hass.bus.async_fire.assert_called_once_with(
            EVENT_DEAD_TIME_UPDATED,
            {"entry_id": DEVICE_ID, "learned_dead_time": None},
        )
        app_with_stale_caches._event_bridge._request_recalculate.assert_called_once()

    @pytest.mark.asyncio
    async def test_noop_when_not_initialized(
        self, app_with_stale_caches: HeatingApplication
    ) -> None:
        """Without an orchestrator, nothing is touched."""
        app_with_stale_caches._orchestrator = None

        await app_with_stale_caches.async_reset_learning()

        assert app_with_stale_caches._lhs_cache == STALE_GLOBAL_LHS
        app_with_stale_caches.hass.bus.async_fire.assert_not_called()
