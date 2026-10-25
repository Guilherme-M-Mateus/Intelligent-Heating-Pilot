"""Shared utility functions for infrastructure adapters."""

from __future__ import annotations

from typing import cast

from homeassistant.core import HomeAssistant, State

WEATHER_DOMAIN = "weather"
# Numeric attributes exposed by weather entities, whose state is a condition string.
WEATHER_ATTR_TEMPERATURE = "temperature"
WEATHER_ATTR_HUMIDITY = "humidity"
WEATHER_ATTR_CLOUD_COVERAGE = "cloud_coverage"
WEATHER_NUMERIC_ATTRIBUTES = (
    WEATHER_ATTR_TEMPERATURE,
    WEATHER_ATTR_HUMIDITY,
    WEATHER_ATTR_CLOUD_COVERAGE,
)


def get_entity_name(hass: HomeAssistant, entity_id: str) -> str:
    """Get the friendly name of an entity, falling back to entity_id.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to get name for

    Returns:
        Friendly name or entity_id if not found
    """
    state = hass.states.get(entity_id)
    if state:
        return cast(str, state.attributes.get("friendly_name", entity_id))
    return entity_id


def read_numeric_state(state: State, weather_attribute: str) -> float | None:
    """Read a numeric value from a sensor state or a weather entity attribute.

    A sensor carries its value in the state, whereas a weather entity's state is a
    condition string (e.g. "cloudy") and the numbers live in attributes. Reading the
    state of a weather entity as a float would always fail.

    Args:
        state: Home Assistant state of the source entity
        weather_attribute: Attribute to read when the entity is a weather entity

    Returns:
        Float value, or None if missing or not numeric
    """
    raw = state.attributes.get(weather_attribute) if state.domain == WEATHER_DOMAIN else state.state
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None
