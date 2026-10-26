"""Shared rule deciding which heating cycles are realistic enough to learn from.

Both the global and the contextual LHS calculators use this rule, so a cycle
rejected by one is never averaged by the other (#223). A cycle that barely
heated (thermostat in safety mode, load shedding, window open...) says nothing
about how fast the room heats and would drag the learned slope down.
"""

from __future__ import annotations

from ..constants import MINIMUM_REALISTIC_LHS
from ..value_objects import HeatingCycle


def is_realistic_learning_cycle(cycle: HeatingCycle) -> bool:
    """Tell whether a cycle heated fast enough to be learned from.

    Args:
        cycle: The heating cycle to check.

    Returns:
        True if its average heating slope is at least MINIMUM_REALISTIC_LHS.
    """
    return cycle.avg_heating_slope >= MINIMUM_REALISTIC_LHS


def filter_realistic_cycles(cycles: list[HeatingCycle]) -> list[HeatingCycle]:
    """Keep only the cycles realistic enough to be learned from.

    Args:
        cycles: Heating cycles to filter.

    Returns:
        The realistic cycles, in their original order.
    """
    return [cycle for cycle in cycles if is_realistic_learning_cycle(cycle)]
