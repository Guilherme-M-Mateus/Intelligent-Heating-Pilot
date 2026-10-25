"""Service for calculating contextual Learning Heating Slope (LHS).

Pure domain logic for grouping cycles by the hour their target was reached
and calculating average heating slopes per hour. No Home Assistant dependencies.
"""

from __future__ import annotations

import logging
from datetime import UTC, tzinfo

from ..constants import MINIMUM_REALISTIC_LHS
from ..value_objects import ContextualLHSByHour, HeatingCycle

_LOGGER = logging.getLogger(__name__)


class ContextualLHSCalculatorService:
    """Calculate contextual LHS grouped by the hour the target was reached.

    The contextual hour is the key shared by the write side (cycles learned
    here) and the read side (anticipation looks up ``target_time.hour``).
    A preheat cycle for a 07:00 slot starts at 05:00 or 06:00 but ends when the
    target is reached, around 07:00. Keying cycles by their end hour therefore
    lets each scheduled slot read the slope learned while preheating for it.

    Responsibilities:
    - Extract the contextual hour from a cycle (its end_time hour)
    - Group cycles by contextual hour
    - Calculate average LHS per hour
    - Handle empty groups gracefully

    Cycle timestamps come from recorder history as naive UTC datetimes, while the
    scheduled slots used for lookups are in local time. ``local_tz`` brings both to
    the same clock; without it the cycle hour is used as stored.

    Pure domain logic with no Home Assistant dependencies.
    """

    def __init__(self, local_tz: tzinfo | None = None) -> None:
        """Initialize the service.

        Args:
            local_tz: Timezone of the scheduled slots. Naive cycle times are read as UTC.
        """
        self._local_tz = local_tz

    def extract_hour_from_cycle(self, cycle: HeatingCycle) -> int:
        """Extract the contextual hour (0-23) of a cycle.

        Uses the end time, i.e. when the target temperature was reached, so the
        key matches the scheduled target hour used for lookups. Using the start
        time would file a preheat cycle under an earlier hour than the slot it
        served, and the slot would never read its own learned slope.

        Args:
            cycle: The heating cycle

        Returns:
            Hour of day (0-23)
        """
        _LOGGER.debug("Extracting hour from cycle ended at %s", cycle.end_time)
        end_time = cycle.end_time
        if self._local_tz is not None:
            end_time = end_time.replace(tzinfo=end_time.tzinfo or UTC).astimezone(self._local_tz)
        hour = end_time.hour
        _LOGGER.debug("Extracted hour: %d", hour)
        return hour

    def group_cycles_by_hour(self, cycles: list[HeatingCycle]) -> dict[int, list[HeatingCycle]]:
        """Group cycles by their contextual hour (see extract_hour_from_cycle).

        Args:
            cycles: All extracted heating cycles

        Returns:
            Mapping {hour: [cycles_ending_at_hour]}
        """
        _LOGGER.debug("Grouping %d cycles by contextual hour", len(cycles))

        grouped: dict[int, list[HeatingCycle]] = {h: [] for h in range(24)}

        for cycle in cycles:
            hour = self.extract_hour_from_cycle(cycle)
            grouped[hour].append(cycle)

        # Log summary
        non_empty = {h: len(c) for h, c in grouped.items() if c}
        _LOGGER.info("Grouped cycles by hour: %s", non_empty)

        return grouped

    def calculate_contextual_lhs_for_hour(
        self, cycles: list[HeatingCycle], target_hour: int
    ) -> float | None:
        """Calculate average LHS for cycles whose contextual hour is target_hour.

        Args:
            cycles: All extracted cycles
            target_hour: Hour (0-23) to filter by

        Returns:
            Average LHS value, or None if no data for this hour or if the
            average is below MINIMUM_REALISTIC_LHS. An unrealistic hour must
            fall back to the global LHS, so it is never reported as learned.

        Raises:
            ValueError: If target_hour not in 0-23
        """
        if not 0 <= target_hour <= 23:
            raise ValueError(f"target_hour must be 0-23, got {target_hour}")

        _LOGGER.debug(
            "Calculating contextual LHS for hour %d from %d cycles", target_hour, len(cycles)
        )

        # Filter cycles that reached their target during target hour
        matching_cycles = [c for c in cycles if self.extract_hour_from_cycle(c) == target_hour]

        avg_lhs = self._average_heating_slope(matching_cycles, target_hour)
        if avg_lhs is None:
            return None

        if avg_lhs < MINIMUM_REALISTIC_LHS:
            _LOGGER.debug(
                "Contextual LHS for hour %d is unrealistic (%.2f°C/h < %.2f°C/h), ignoring it",
                target_hour,
                avg_lhs,
                MINIMUM_REALISTIC_LHS,
            )
            return None

        _LOGGER.info(
            "Calculated contextual LHS for hour %d: %.2f°C/h from %d cycles",
            target_hour,
            avg_lhs,
            len(matching_cycles),
        )

        return avg_lhs

    def calculate_contextual_lhs_by_hour(self, cycles: list[HeatingCycle]) -> ContextualLHSByHour:
        """Calculate contextual LHS for all 24 hours, keeping rejected hours apart.

        Callers need to know which hours were rejected as unrealistic, because a
        slope stored for them earlier must be dropped so they use the global LHS.
        Hours without cycles are neither learned nor rejected.

        Args:
            cycles: All extracted cycles

        Returns:
            Realistic averages by hour, and the hours rejected below MINIMUM_REALISTIC_LHS.
        """
        _LOGGER.debug("Calculating contextual LHS for all 24 hours from %d cycles", len(cycles))

        learned: dict[int, float] = {}
        rejected: set[int] = set()
        for hour, hour_cycles in self.group_cycles_by_hour(cycles).items():
            avg_lhs = self._average_heating_slope(hour_cycles, hour)
            if avg_lhs is None:
                continue
            if avg_lhs < MINIMUM_REALISTIC_LHS:
                rejected.add(hour)
            else:
                learned[hour] = avg_lhs

        _LOGGER.info(
            "Contextual LHS learned for %d hours; %d hours rejected below %.2f°C/h %s",
            len(learned),
            len(rejected),
            MINIMUM_REALISTIC_LHS,
            sorted(rejected),
        )

        return ContextualLHSByHour(learned=learned, rejected_hours=frozenset(rejected))

    def _average_heating_slope(self, cycles: list[HeatingCycle], hour: int) -> float | None:
        """Average the positive heating slopes of the cycles of one hour.

        Cycles where temperature did not rise carry no useful learning data
        about heating speed, so they are left out.

        Args:
            cycles: Cycles already filtered to the hour
            hour: Hour (0-23), for logging

        Returns:
            Average slope in °C/hour, or None if no cycle has a positive slope.
        """
        if not cycles:
            _LOGGER.debug("No cycles found for hour %d", hour)
            return None

        lhs_values = [c.avg_heating_slope for c in cycles if c.avg_heating_slope > 0]
        if not lhs_values:
            _LOGGER.debug("No cycles with positive heating slope for hour %d", hour)
            return None

        return sum(lhs_values) / len(lhs_values)

    def calculate_all_contextual_lhs(self, cycles: list[HeatingCycle]) -> dict[int, float | None]:
        """Calculate contextual LHS for all 24 hours.

        Args:
            cycles: All extracted cycles

        Returns:
            Mapping {hour: avg_lhs_value_or_none}. Hours without cycles and
            hours rejected as unrealistic are both None.
        """
        return self.calculate_contextual_lhs_by_hour(cycles).as_hour_map()
