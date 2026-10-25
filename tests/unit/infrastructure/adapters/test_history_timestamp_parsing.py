"""Regression tests for recorder history timestamp parsing (issue #179).

Home Assistant only bumps ``last_changed`` when the state string changes. For a
climate entity the state is the hvac_mode, so attribute-only updates (current
temperature, target temperature, hvac_action) keep the same ``last_changed``
and only ``last_updated`` moves.
"""

from datetime import datetime

import pytest

from custom_components.intelligent_heating_pilot.infrastructure.adapters.climate_data_reader import (
    HAClimateDataReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.sensor_data_reader import (
    HASensorDataReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.weather_data_reader import (
    HAWeatherDataReader,
)

READERS = [HAClimateDataReader, HASensorDataReader, HAWeatherDataReader]
MODE_CHANGE = "2024-01-15T00:00:00+00:00"
ATTRIBUTE_UPDATE = "2024-01-15T12:30:00+00:00"


@pytest.mark.parametrize("reader", READERS)
def test_last_updated_wins_when_state_string_unchanged(reader):
    """Attribute-only updates must keep their own timestamp."""
    record = {"last_changed": MODE_CHANGE, "last_updated": ATTRIBUTE_UPDATE}

    assert reader._parse_timestamp(record) == datetime(2024, 1, 15, 12, 30)


@pytest.mark.parametrize("reader", READERS)
def test_distinct_samples_keep_distinct_timestamps(reader):
    """Samples sharing last_changed must not collapse to one timestamp."""
    records = [
        {
            "state": "heat",
            "last_changed": MODE_CHANGE,
            "last_updated": f"2024-01-15T12:{minute:02d}:00+00:00",
        }
        for minute in (0, 5, 10)
    ]

    assert len({reader._parse_timestamp(r) for r in records}) == 3


@pytest.mark.parametrize("reader", READERS)
def test_falls_back_to_last_changed(reader):
    """Records lacking last_updated still parse via last_changed."""
    assert reader._parse_timestamp({"last_changed": MODE_CHANGE}) == datetime(2024, 1, 15, 0, 0)
