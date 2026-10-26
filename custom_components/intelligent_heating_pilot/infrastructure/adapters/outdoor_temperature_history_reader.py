"""Home Assistant outdoor temperature history adapter.

Feeds the configured outdoor source (sensor or weather entity) into cycle
extraction, so each heating cycle records the outdoor temperature it ran in.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from ...domain.interfaces.historical_data_adapter_interface import IHistoricalDataAdapter
from ...domain.value_objects import (
    HistoricalDataKey,
    HistoricalDataSet,
    HistoricalMeasurement,
)
from .sensor_data_reader import HASensorDataReader
from .utils import WEATHER_DOMAIN, temperature_unit, to_celsius
from .weather_data_reader import HAWeatherDataReader

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..recorder_queue import RecorderAccessQueue

_LOGGER = logging.getLogger(__name__)


class HAOutdoorTemperatureHistoryReader(IHistoricalDataAdapter):
    """Reads the outdoor temperature history of the configured outdoor source.

    Cycle extraction asks every adapter about the VTherm entity. This adapter is
    bound to the outdoor source instead: it ignores the requested ``entity_id`` and
    only answers ``OUTDOOR_TEMP``, with values converted to Celsius.

    The outdoor temperature is optional, so a failed history query yields an empty
    dataset rather than aborting the extraction of the whole cycle.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        recorder_queue: RecorderAccessQueue,
        outdoor_entity_id: str,
    ) -> None:
        """Initialize the reader.

        Args:
            hass: Home Assistant instance
            recorder_queue: Shared FIFO queue to serialize recorder access (MANDATORY)
            outdoor_entity_id: Outdoor temperature sensor or weather entity
        """
        self._outdoor_entity_id = outdoor_entity_id
        self._domain = outdoor_entity_id.split(".", 1)[0]
        self._reader: IHistoricalDataAdapter = (
            HAWeatherDataReader(hass, recorder_queue)
            if self._domain == WEATHER_DOMAIN
            else HASensorDataReader(hass, recorder_queue)
        )
        _LOGGER.debug("Initialized outdoor temperature history for %s", outdoor_entity_id)

    async def fetch_historical_data(
        self,
        entity_id: str,
        data_key: HistoricalDataKey,
        start_time: datetime,
        end_time: datetime,
    ) -> HistoricalDataSet:
        """Fetch the outdoor temperature history, in Celsius.

        Args:
            entity_id: Ignored; the adapter is bound to the outdoor source
            data_key: Only OUTDOOR_TEMP is answered
            start_time: Start of historical period
            end_time: End of historical period

        Returns:
            HistoricalDataSet with OUTDOOR_TEMP measurements, possibly empty
        """
        if data_key != HistoricalDataKey.OUTDOOR_TEMP:
            return HistoricalDataSet(data={})

        try:
            raw = await self._reader.fetch_historical_data(
                self._outdoor_entity_id, data_key, start_time, end_time
            )
        except ValueError as exc:
            _LOGGER.warning(
                "Outdoor temperature history unavailable for %s: %s", self._outdoor_entity_id, exc
            )
            return HistoricalDataSet(data={})

        measurements = self._to_celsius(raw.data.get(data_key, []))
        return HistoricalDataSet(data={data_key: measurements} if measurements else {})

    async def fetch_all_historical_data(
        self,
        entity_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> HistoricalDataSet:
        """Fetch the outdoor temperature history in one query (its only key)."""
        return await self.fetch_historical_data(
            entity_id, HistoricalDataKey.OUTDOOR_TEMP, start_time, end_time
        )

    def _to_celsius(self, measurements: list[HistoricalMeasurement]) -> list[HistoricalMeasurement]:
        """Convert measurements to Celsius, dropping those in an unknown unit."""
        converted = []
        unknown_units: set[str | None] = set()
        for measurement in measurements:
            if not isinstance(measurement.value, int | float) or isinstance(
                measurement.value, bool
            ):
                continue
            unit = temperature_unit(self._domain, measurement.attributes)
            value = to_celsius(float(measurement.value), unit)
            if value is None:
                unknown_units.add(unit)
                continue
            converted.append(
                HistoricalMeasurement(
                    timestamp=measurement.timestamp,
                    value=value,
                    attributes={},
                    entity_id=measurement.entity_id,
                )
            )
        if unknown_units:
            _LOGGER.warning(
                "Ignored outdoor temperatures of %s in unsupported unit(s) %s",
                self._outdoor_entity_id,
                sorted(str(unit) for unit in unknown_units),
            )
        return converted
