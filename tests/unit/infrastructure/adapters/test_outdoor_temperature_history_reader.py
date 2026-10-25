"""Tests for HAOutdoorTemperatureHistoryReader adapter."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.intelligent_heating_pilot.domain.value_objects import (
    HistoricalDataKey,
    HistoricalDataSet,
    HistoricalMeasurement,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.outdoor_temperature_history_reader import (
    HAOutdoorTemperatureHistoryReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.sensor_data_reader import (
    HASensorDataReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.weather_data_reader import (
    HAWeatherDataReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.recorder_queue import (
    RecorderAccessQueue,
)

START = datetime(2026, 1, 1, 0, 0)
END = datetime(2026, 1, 2, 0, 0)


def _reader(entity_id: str, measurements: list[HistoricalMeasurement]) -> tuple:
    reader = HAOutdoorTemperatureHistoryReader(MagicMock(), RecorderAccessQueue(), entity_id)
    inner = AsyncMock(
        return_value=HistoricalDataSet(data={HistoricalDataKey.OUTDOOR_TEMP: measurements})
    )
    reader._reader.fetch_historical_data = inner  # type: ignore[method-assign]
    return reader, inner


def _measurement(value: float, **attributes: str) -> HistoricalMeasurement:
    return HistoricalMeasurement(START, value, attributes, "outdoor")


def test_weather_entity_uses_weather_reader():
    reader = HAOutdoorTemperatureHistoryReader(MagicMock(), RecorderAccessQueue(), "weather.home")
    assert isinstance(reader._reader, HAWeatherDataReader)


def test_sensor_entity_uses_sensor_reader():
    reader = HAOutdoorTemperatureHistoryReader(MagicMock(), RecorderAccessQueue(), "sensor.out")
    assert isinstance(reader._reader, HASensorDataReader)


@pytest.mark.asyncio
async def test_queries_the_outdoor_entity_not_the_requested_one():
    """Extraction asks about the VTherm; the outdoor source is what gets queried."""
    reader, inner = _reader("sensor.outdoor", [_measurement(5.0)])

    await reader.fetch_all_historical_data("climate.living_room", START, END)

    assert inner.call_args.args[0] == "sensor.outdoor"


@pytest.mark.asyncio
async def test_other_keys_are_not_answered():
    reader, inner = _reader("sensor.outdoor", [_measurement(5.0)])

    result = await reader.fetch_historical_data(
        "climate.living_room", HistoricalDataKey.INDOOR_TEMP, START, END
    )

    assert result.data == {}
    inner.assert_not_called()


@pytest.mark.asyncio
async def test_fahrenheit_sensor_history_is_converted():
    reader, _ = _reader("sensor.outdoor", [_measurement(41.0, unit_of_measurement="°F")])

    result = await reader.fetch_all_historical_data("climate.room", START, END)

    assert result.data[HistoricalDataKey.OUTDOOR_TEMP][0].value == pytest.approx(5.0)


@pytest.mark.asyncio
async def test_fahrenheit_weather_history_is_converted():
    reader, _ = _reader("weather.home", [_measurement(50.0, temperature_unit="°F")])

    result = await reader.fetch_all_historical_data("climate.room", START, END)

    assert result.data[HistoricalDataKey.OUTDOOR_TEMP][0].value == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_unknown_unit_is_dropped():
    reader, _ = _reader(
        "sensor.outdoor",
        [_measurement(41.0, unit_of_measurement="bananas"), _measurement(3.0)],
    )

    result = await reader.fetch_all_historical_data("climate.room", START, END)

    assert [m.value for m in result.data[HistoricalDataKey.OUTDOOR_TEMP]] == [3.0]


@pytest.mark.asyncio
async def test_failed_history_query_does_not_abort_extraction():
    """Outdoor data is optional: a failing query yields no data, not an error."""
    reader, inner = _reader("sensor.outdoor", [])
    inner.side_effect = ValueError("recorder unavailable")

    result = await reader.fetch_all_historical_data("climate.room", START, END)

    assert result.data == {}
