"""Timeslot reader interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..value_objects import ScheduledTimeslot


class ITimeslotReader(ABC):
    """Contract for reading the next heating timeslot from any source.

    Implementations of this interface retrieve the next target time from
    various sources: HACS scheduler entities, native HA schedule entities,
    or datetime/input_datetime/sensor entities.
    """

    @abstractmethod
    async def get_next_timeslot(self) -> ScheduledTimeslot | None:
        """Retrieve the next scheduled heating timeslot.

        Returns:
            The next schedule timeslot, or None if no timeslots are scheduled.
        """
        pass

    @abstractmethod
    async def is_timeslot_source_enabled(self, entity_id: str) -> bool:
        """Check if a specific timeslot source entity is enabled.

        Args:
            entity_id: The entity ID to check

        Returns:
            True if the source is enabled, False otherwise
        """
        pass
