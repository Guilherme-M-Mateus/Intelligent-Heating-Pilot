"""Service for calculating global Learning Heating Slope (LHS).

Pure domain logic for calculating average heating slope from all cycles,
regardless of time of day. No Home Assistant dependencies.
"""

from __future__ import annotations

import logging

from ..constants import DEFAULT_LEARNED_SLOPE, MINIMUM_REALISTIC_LHS
from ..value_objects import HeatingCycle
from .learning_cycle_filter import filter_realistic_cycles

_LOGGER = logging.getLogger(__name__)


class GlobalLHSCalculatorService:
    """Calculate global LHS from all heating cycles.

    Responsibilities:
    - Calculate average heating slope from all realistic cycles
    - Return default slope when no realistic cycle is available
    - Handle edge cases gracefully

    Pure domain logic with no Home Assistant dependencies.
    """

    def calculate_global_lhs(self, cycles: list[HeatingCycle]) -> float:
        """Calculate average LHS from all heating cycles.

        Args:
            cycles: List of all heating cycles to analyze

        Returns:
            float: Average heating slope in °C/hour, or DEFAULT_LEARNED_SLOPE if no
            realistic cycle remains

        Calculation:
            Cycles below MINIMUM_REALISTIC_LHS are left out (same rule as the
            contextual LHS), then the remaining slopes are averaged.
        """
        _LOGGER.debug("Calculating global LHS from %d cycles", len(cycles))

        if not cycles:
            _LOGGER.info(
                "No cycles available for global LHS calculation, returning default slope: %.2f°C/h",
                DEFAULT_LEARNED_SLOPE,
            )
            return DEFAULT_LEARNED_SLOPE

        # Same rule as the contextual LHS: cycles that barely heated carry no
        # useful learning data about heating speed (#223)
        lhs_values = [cycle.avg_heating_slope for cycle in filter_realistic_cycles(cycles)]

        if not lhs_values:
            _LOGGER.info(
                "No realistic cycle (>= %.2f°C/h), returning default: %.2f°C/h",
                MINIMUM_REALISTIC_LHS,
                DEFAULT_LEARNED_SLOPE,
            )
            return DEFAULT_LEARNED_SLOPE

        global_lhs = sum(lhs_values) / len(lhs_values)

        _LOGGER.info(
            "Calculated global LHS: %.2f°C/h from %d realistic cycles out of %d",
            global_lhs,
            len(lhs_values),
            len(cycles),
        )
        _LOGGER.debug("Global LHS calculation complete")

        return global_lhs
