"""pytest-bdd step definitions for outdoor conditions scenarios.

Covers the path from configuration to the environment seen by the prediction:
the configured outdoor sources are read through HADeviceConfigReader, then
HAEnvironmentReader turns sensor or weather entity states into an EnvironmentState.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import State
from pytest_bdd import given, parsers, scenarios, then, when

from custom_components.intelligent_heating_pilot.const import (
    CONF_CLOUD_COVER_ENTITY,
    CONF_HUMIDITY_OUT_ENTITY,
    CONF_TEMPERATURE_OUT_ENTITY,
    CONF_VTHERM_ENTITY,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.device_config_reader import (
    HADeviceConfigReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.adapters.environment_reader import (
    HAEnvironmentReader,
)
from custom_components.intelligent_heating_pilot.infrastructure.event_bridge import (
    HAEventBridge,
)

scenarios("outdoor_conditions.feature")

VTHERM_ENTITY_ID = "climate.living_room"
INDOOR_TEMPERATURE = 19.0


@pytest.fixture
def outdoor_context() -> dict:
    """Shared context: config entry data, HA states and results."""
    return {
        "data": {CONF_VTHERM_ENTITY: VTHERM_ENTITY_ID},
        "states": {
            VTHERM_ENTITY_ID: State(
                VTHERM_ENTITY_ID, "heat", {"current_temperature": INDOOR_TEMPERATURE}
            )
        },
    }


def _make_hass(outdoor_context: dict) -> Mock:
    hass = Mock()
    hass.states.get = Mock(side_effect=outdoor_context["states"].get)
    return hass


# ------------------------------------------------------------------
# Given
# ------------------------------------------------------------------


@given(parsers.parse('the outdoor temperature source is "{entity_id}"'))
def outdoor_temperature_source(outdoor_context: dict, entity_id: str) -> None:
    """GIVEN: The user configured an outdoor temperature source."""
    outdoor_context["data"][CONF_TEMPERATURE_OUT_ENTITY] = entity_id


@given(parsers.parse('the outdoor humidity source is "{entity_id}"'))
def outdoor_humidity_source(outdoor_context: dict, entity_id: str) -> None:
    """GIVEN: The user configured an outdoor humidity source."""
    outdoor_context["data"][CONF_HUMIDITY_OUT_ENTITY] = entity_id


@given(parsers.parse('the cloud coverage source is "{entity_id}"'))
def cloud_coverage_source(outdoor_context: dict, entity_id: str) -> None:
    """GIVEN: The user configured a cloud coverage source."""
    outdoor_context["data"][CONF_CLOUD_COVER_ENTITY] = entity_id


@given(parsers.parse('"{entity_id}" reports {value:f} "{unit}"'))
def sensor_reports(outdoor_context: dict, entity_id: str, value: float, unit: str) -> None:
    """GIVEN: A sensor reports a value in its unit."""
    outdoor_context["states"][entity_id] = State(
        entity_id, str(value), {"unit_of_measurement": unit}
    )


@given(
    parsers.parse(
        '"{entity_id}" is "{condition}" with temperature {temperature:f} "{unit}", '
        "humidity {humidity:d} and cloud coverage {cloud:d}"
    )
)
def weather_reports(
    outdoor_context: dict,
    entity_id: str,
    condition: str,
    temperature: float,
    unit: str,
    humidity: int,
    cloud: int,
) -> None:
    """GIVEN: A weather entity reports its condition and numeric attributes."""
    outdoor_context["states"][entity_id] = State(
        entity_id,
        condition,
        {
            "temperature": temperature,
            "temperature_unit": unit,
            "humidity": humidity,
            "cloud_coverage": cloud,
        },
    )


@given(parsers.parse('IHP monitors the outdoor source "{entity_id}"'))
def ihp_monitors(outdoor_context: dict, entity_id: str) -> None:
    """GIVEN: The event bridge listens to the outdoor source."""
    bridge = HAEventBridge(
        hass=Mock(),
        orchestrator=AsyncMock(),
        vtherm_entity_id=VTHERM_ENTITY_ID,
        scheduler_entity_ids=[],
        monitored_entity_ids=[entity_id],
    )
    bridge._request_recalculate = Mock()  # type: ignore[method-assign]
    with patch(
        "custom_components.intelligent_heating_pilot.infrastructure.event_bridge."
        "async_track_state_change_event"
    ) as track:
        bridge.setup_listeners()
    outdoor_context["bridge"] = bridge
    outdoor_context["listener"] = track.call_args.args[2]
    outdoor_context["monitored_entity_id"] = entity_id


# ------------------------------------------------------------------
# When
# ------------------------------------------------------------------


@when("IHP reads the current environment")
def read_environment(outdoor_context: dict) -> None:
    """WHEN: IHP reads its configuration, then the current environment."""
    hass = _make_hass(outdoor_context)
    config_entry = Mock(entry_id="entry", data=outdoor_context["data"], options={})

    async def _read() -> object:
        config = await HADeviceConfigReader(hass, config_entry).get_device_config("entry")
        reader = HAEnvironmentReader(
            hass,
            config.vtherm_entity_id,
            outdoor_temp_entity_id=config.temperature_out_entity_id,
            humidity_out_entity_id=config.humidity_out_entity_id,
            cloud_cover_entity_id=config.cloud_cover_entity_id,
        )
        return await reader.get_current_environment()

    outdoor_context["environment"] = asyncio.run(_read())


@when(parsers.parse("the outdoor temperature goes {values} °C"))
def outdoor_temperature_goes(outdoor_context: dict, values: str) -> None:
    """WHEN: The outdoor sensor reports a sequence of temperatures."""
    entity_id = outdoor_context["monitored_entity_id"]
    attributes = {"device_class": "temperature", "unit_of_measurement": "°C"}
    states = [State(entity_id, v.strip(), attributes) for v in values.split(",")]
    triggers = []
    for old_state, new_state in zip(states, states[1:], strict=False):
        recalculate = outdoor_context["bridge"]._request_recalculate
        recalculate.reset_mock()
        event = Mock(data={"entity_id": entity_id, "old_state": old_state, "new_state": new_state})
        outdoor_context["listener"](event)
        triggers.append(recalculate.called)
    outdoor_context["triggers"] = triggers


# ------------------------------------------------------------------
# Then
# ------------------------------------------------------------------


@then(parsers.parse("the outdoor temperature is {expected:f} °C"))
def outdoor_temperature_is(outdoor_context: dict, expected: float) -> None:
    """THEN: The environment carries the outdoor temperature in Celsius."""
    assert outdoor_context["environment"].outdoor_temp == pytest.approx(expected)


@then("the outdoor temperature is unknown")
def outdoor_temperature_unknown(outdoor_context: dict) -> None:
    """THEN: No outdoor temperature reaches the prediction."""
    assert outdoor_context["environment"].outdoor_temp is None


@then(parsers.parse("the outdoor humidity is {expected:d}"))
def outdoor_humidity_is(outdoor_context: dict, expected: int) -> None:
    """THEN: The environment carries the outdoor humidity."""
    assert outdoor_context["environment"].outdoor_humidity == pytest.approx(expected)


@then(parsers.parse("the cloud coverage is {expected:d}"))
def cloud_coverage_is(outdoor_context: dict, expected: int) -> None:
    """THEN: The environment carries the cloud coverage."""
    assert outdoor_context["environment"].cloud_coverage == pytest.approx(expected)


@then("only the last step triggers a recalculation")
def only_last_step_triggers(outdoor_context: dict) -> None:
    """THEN: Small steps add up until the drift is worth a recalculation."""
    triggers = outdoor_context["triggers"]
    assert triggers == [False] * (len(triggers) - 1) + [True]
