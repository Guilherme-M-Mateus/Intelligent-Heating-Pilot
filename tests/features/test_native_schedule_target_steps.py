"""pytest-bdd step definitions for the native schedule target temperature (#188).

A native ``schedule.*`` entity only tells when the next ON slot starts, not which
temperature it applies. While the schedule is off, the thermostat holds its
off-period setpoint, so IHP must anticipate the comfort preset instead.
"""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from custom_components.intelligent_heating_pilot.infrastructure.adapters.scheduler_reader import (
    HASchedulerReader,
)

scenarios("native_schedule_target.feature")

_NEXT_ON_EVENT_DATE = "2024-01-15"
_TIMEZONE_OFFSET = "+01:00"


@pytest.fixture
def schedule_context() -> dict:
    """Shared context for native schedule BDD scenarios."""
    return {"states": {}}


def _make_state(entity_id: str, state_value: str, attributes: dict) -> Mock:
    state = Mock()
    state.entity_id = entity_id
    state.state = state_value
    state.attributes = attributes
    return state


@given(
    parsers.parse('a native schedule "{entity_id}" that is off with its next ON event at {time}')
)
def native_schedule_off(schedule_context: dict, entity_id: str, time: str) -> None:
    """GIVEN: A native schedule outside its active block, next ON at ``time``."""
    schedule_context["schedule_id"] = entity_id
    schedule_context["states"][entity_id] = _make_state(
        entity_id,
        "off",
        {
            "next_event": f"{_NEXT_ON_EVENT_DATE}T{time}:00{_TIMEZONE_OFFSET}",
            "friendly_name": "Heating",
        },
    )


@given(parsers.parse('the thermostat "{entity_id}" currently targets {temp:f}°C'))
def thermostat_current_target(schedule_context: dict, entity_id: str, temp: float) -> None:
    """GIVEN: The thermostat holds its off-period (eco) setpoint."""
    schedule_context["vtherm_id"] = entity_id
    schedule_context["states"][entity_id] = _make_state(
        entity_id, "heat", {"temperature": temp, "preset_mode": "eco"}
    )


@given(parsers.parse("the thermostat comfort preset is {temp:f}°C"))
def thermostat_comfort_preset(schedule_context: dict, temp: float) -> None:
    """GIVEN: The VTherm exposes its comfort preset temperature."""
    vtherm_state = schedule_context["states"][schedule_context["vtherm_id"]]
    vtherm_state.attributes["preset_temperatures"] = {"eco_temp": 17.0, "comfort_temp": temp}


@given("the thermostat has no comfort preset")
def thermostat_without_comfort_preset(schedule_context: dict) -> None:
    """GIVEN: The VTherm exposes no comfort preset temperature."""
    vtherm_state = schedule_context["states"][schedule_context["vtherm_id"]]
    vtherm_state.attributes["preset_temperatures"] = {"eco_temp": 17.0}


@when("IHP reads the next scheduled timeslot")
def read_next_timeslot(schedule_context: dict) -> None:
    """WHEN: The scheduler reader resolves the next timeslot."""
    hass = Mock()
    hass.is_running = True
    hass.states.get.side_effect = schedule_context["states"].get
    reader = HASchedulerReader(
        hass,
        [schedule_context["schedule_id"]],
        vtherm_entity_id=schedule_context["vtherm_id"],
    )
    schedule_context["timeslot"] = asyncio.run(reader.get_next_timeslot())


@then(parsers.parse("the timeslot starts at {time}"))
def timeslot_starts_at(schedule_context: dict, time: str) -> None:
    """THEN: The timeslot starts at the native schedule next ON event."""
    timeslot = schedule_context["timeslot"]
    assert timeslot is not None
    assert timeslot.target_time.strftime("%H:%M") == time


@then(parsers.parse("the timeslot target temperature is {temp:f}°C"))
def timeslot_target_temperature(schedule_context: dict, temp: float) -> None:
    """THEN: The timeslot targets the expected comfort temperature."""
    timeslot = schedule_context["timeslot"]
    assert timeslot is not None
    assert timeslot.target_temp == temp
