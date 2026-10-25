"""Tests for the outdoor temperature recorded with each heating cycle."""

from datetime import datetime, timedelta

import pytest

from custom_components.intelligent_heating_pilot.domain.services.heating_cycle_service import (
    HeatingCycleService,
)
from custom_components.intelligent_heating_pilot.domain.value_objects import HeatingCycle
from custom_components.intelligent_heating_pilot.domain.value_objects.historical_data import (
    HistoricalDataKey,
    HistoricalDataSet,
    HistoricalMeasurement,
)

T0 = datetime(2024, 1, 1, 6, 0, 0)


def _outdoor(*readings: tuple[int, float | str]) -> dict:
    """Build outdoor readings as (minutes after T0, value)."""
    return {
        HistoricalDataKey.OUTDOOR_TEMP: [
            HistoricalMeasurement(T0 + timedelta(minutes=minutes), value, {}, "sensor.outdoor")
            for minutes, value in readings
        ]
    }


def _average(data: dict, start_minutes: int, end_minutes: int) -> float | None:
    return HeatingCycleService._compute_average_outdoor_temp(
        data, T0 + timedelta(minutes=start_minutes), T0 + timedelta(minutes=end_minutes)
    )


class TestComputeAverageOutdoorTemp:
    """Time-weighted average of a step-function outdoor history."""

    def test_reading_before_start_holds_until_the_next_one(self):
        # 4°C for 10 min, then 6°C for 15 min -> (40 + 90) / 25
        assert _average(_outdoor((-30, 4.0), (20, 6.0)), 10, 35) == pytest.approx(5.2)

    def test_single_reading_before_window_covers_it(self):
        assert _average(_outdoor((-60, 3.0)), 0, 30) == pytest.approx(3.0)

    def test_window_without_earlier_reading_starts_at_first_reading(self):
        # Nothing known before minute 10: only 10..30 counts
        assert _average(_outdoor((10, 2.0), (20, 4.0)), 0, 30) == pytest.approx(3.0)

    def test_readings_after_window_are_ignored(self):
        assert _average(_outdoor((0, 5.0), (40, -10.0)), 0, 30) == pytest.approx(5.0)

    def test_no_outdoor_history_gives_none(self):
        assert _average({}, 0, 30) is None

    def test_only_readings_after_window_gives_none(self):
        assert _average(_outdoor((40, 5.0)), 0, 30) is None

    def test_non_numeric_readings_are_skipped(self):
        assert _average(_outdoor((0, "unavailable"), (0, 7.0)), 0, 30) == pytest.approx(7.0)


class TestIndoorOutdoorDelta:
    """The heat-loss gap of a cycle uses its midpoint indoor temperature."""

    def _cycle(self, avg_outdoor_temp: float | None) -> HeatingCycle:
        return HeatingCycle(
            device_id="climate.room",
            start_time=T0,
            end_time=T0 + timedelta(hours=1),
            target_temp=21.0,
            end_temp=20.0,
            start_temp=18.0,
            avg_outdoor_temp=avg_outdoor_temp,
        )

    def test_delta_is_midpoint_minus_outdoor(self):
        assert self._cycle(5.0).indoor_outdoor_delta == pytest.approx(14.0)

    def test_delta_is_none_without_outdoor_temperature(self):
        assert self._cycle(None).indoor_outdoor_delta is None


@pytest.mark.asyncio
async def test_extracted_cycle_records_outdoor_average():
    """A cycle extracted from history carries the outdoor average of its window."""
    service = HeatingCycleService(
        temp_delta_threshold=0.5,
        cycle_split_duration_minutes=0,
        min_cycle_duration_minutes=5,
        max_cycle_duration_minutes=300,
    )

    def at(minutes: int, value, **attrs) -> HistoricalMeasurement:
        return HistoricalMeasurement(T0 + timedelta(minutes=minutes), value, attrs, "climate.room")

    off = {"hvac_action": "off", "hvac_mode": "off"}
    heating = {"hvac_action": "heating", "hvac_mode": "heat"}
    dataset = HistoricalDataSet(
        data={
            HistoricalDataKey.INDOOR_TEMP: [at(0, 18.0), at(10, 19.0), at(25, 19.2), at(35, 19.6)],
            HistoricalDataKey.TARGET_TEMP: [at(m, 20.0) for m in (0, 10, 25, 35)],
            HistoricalDataKey.HEATING_STATE: [
                at(0, False, **off),
                at(10, True, **heating),
                at(25, True, **heating),
                at(35, False, **heating),
                at(45, False, **{**off, "hvac_mode": "heat"}),
            ],
            **_outdoor((-30, 4.0), (20, 6.0)),
        }
    )

    cycles = await service.extract_heating_cycles(
        "climate.room", dataset, T0, T0 + timedelta(minutes=50)
    )

    assert len(cycles) == 1
    assert cycles[0].avg_outdoor_temp == pytest.approx(5.2)
