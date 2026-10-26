"""Unit tests for the shared rule that keeps only cycles realistic for learning (#223)."""

from __future__ import annotations

from datetime import timedelta

from custom_components.intelligent_heating_pilot.domain.constants import MINIMUM_REALISTIC_LHS
from custom_components.intelligent_heating_pilot.domain.services.learning_cycle_filter import (
    filter_realistic_cycles,
    is_realistic_learning_cycle,
)
from custom_components.intelligent_heating_pilot.domain.value_objects.heating import HeatingCycle
from tests.unit.domain.fixtures import create_test_heating_cycle, get_test_datetime

DEVICE_ID = "climate.test_vtherm"


def _cycle_with_slope(slope: float) -> HeatingCycle:
    """Create a one-hour cycle whose average heating slope equals ``slope``."""
    return create_test_heating_cycle(DEVICE_ID, get_test_datetime(), temp_increase=slope)


def test_cycle_at_realistic_minimum_is_kept() -> None:
    """A slope exactly at MINIMUM_REALISTIC_LHS is still realistic."""
    start_time = get_test_datetime()
    # Start from 0 so the slope is exactly the threshold (no float rounding)
    cycle = HeatingCycle(
        device_id=DEVICE_ID,
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        target_temp=MINIMUM_REALISTIC_LHS,
        end_temp=MINIMUM_REALISTIC_LHS,
        start_temp=0.0,
    )

    assert is_realistic_learning_cycle(cycle)


def test_cycle_below_realistic_minimum_is_rejected() -> None:
    """A cycle that barely heated (e.g. safety mode or load shedding) is not learned from."""
    assert not is_realistic_learning_cycle(_cycle_with_slope(MINIMUM_REALISTIC_LHS - 0.05))


def test_non_positive_cycles_are_rejected() -> None:
    """Cycles where temperature did not rise carry no learning data."""
    assert not is_realistic_learning_cycle(_cycle_with_slope(0.0))
    assert not is_realistic_learning_cycle(_cycle_with_slope(-1.0))


def test_filter_keeps_only_realistic_cycles_in_order() -> None:
    """Filtering keeps realistic cycles and preserves their order."""
    fast = _cycle_with_slope(3.0)
    slow = _cycle_with_slope(0.1)
    medium = _cycle_with_slope(1.0)

    assert filter_realistic_cycles([fast, slow, medium]) == [fast, medium]


def test_filter_empty_list_returns_empty_list() -> None:
    """No cycles in, no cycles out."""
    assert filter_realistic_cycles([]) == []
