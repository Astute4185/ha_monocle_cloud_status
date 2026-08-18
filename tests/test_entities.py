"""Unit tests for Monocle entities and platform setup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from custom_components.ha_monocle_cloud_status import (
    binary_sensor,
    button,
    number,
    select,
    sensor,
)
from custom_components.ha_monocle_cloud_status.binary_sensor import (
    MonocleOnlineBinarySensor,
)
from custom_components.ha_monocle_cloud_status.button import MonocleApplyOverrideButton
from custom_components.ha_monocle_cloud_status.client import (
    MonocleClientError,
    MonocleState,
)
from custom_components.ha_monocle_cloud_status.number import (
    MonocleOverrideMinutesNumber,
)
from custom_components.ha_monocle_cloud_status.select import MonocleOverrideModeSelect
from custom_components.ha_monocle_cloud_status.sensor import SENSORS, MonocleSensor
import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory


def _coordinator(**state_values):
    state = MonocleState(**state_values)
    coordinator = MagicMock()
    coordinator.client.state = state
    coordinator.client.async_save_override = AsyncMock()
    coordinator.client.async_remove_override = AsyncMock()
    coordinator.location_id = "42"
    coordinator.last_update_success = True
    coordinator.selected_override_mode = "None"
    coordinator.selected_override_minutes = 60
    coordinator.async_update_listeners = MagicMock()
    return coordinator


def _entry(coordinator):
    return SimpleNamespace(
        entry_id="entry-id",
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )


@pytest.mark.parametrize(
    ("platform", "expected_count"),
    [
        (binary_sensor, 1),
        (button, 1),
        (number, 1),
        (select, 1),
        (sensor, len(SENSORS)),
    ],
)
async def test_platform_setup_adds_entities(platform, expected_count: int) -> None:
    """Every platform registers its fixed entity set."""
    coordinator = _coordinator()
    add_entities = MagicMock()
    await platform.async_setup_entry(MagicMock(), _entry(coordinator), add_entities)
    add_entities.assert_called_once()
    entities = list(add_entities.call_args.args[0])
    assert len(entities) == expected_count


def test_binary_sensor_and_device_info() -> None:
    """Online state, availability, and device metadata reflect coordinator state."""
    coordinator = _coordinator(connected=True, device_online=True)
    entity = MonocleOnlineBinarySensor(coordinator, _entry(coordinator))
    assert entity.is_on is True
    assert entity.available is True
    assert entity.unique_id == "entry-id_device_online"
    assert entity.device_info["identifiers"] == {("ha_monocle_cloud_status", "42")}


def test_sensors_expose_values_and_unavailable_state() -> None:
    """Sensor descriptions map telemetry into native values."""
    coordinator = _coordinator(
        connected=True,
        mains_pwr=100.5,
        solar_pwr=200.0,
        house_pwr=50.0,
        battery_pwr=-10.0,
        load_state="on",
        override_mode="off",
    )
    entry = _entry(coordinator)
    entities = {
        description.key: MonocleSensor(coordinator, entry, description)
        for description in SENSORS
    }

    assert entities["mains_power"].native_value == 100.5
    assert entities["solar_power"].native_value == 200.0
    assert entities["house_power"].native_value == 50.0
    assert entities["battery_power"].native_value == -10.0
    assert entities["load_state"].native_value == "On"
    assert entities["override_mode"].native_value == "Off"
    assert entities["mains_power"].available is True

    coordinator.client.state.connected = False
    assert entities["mains_power"].available is False


async def test_number_and_select_update_draft_state() -> None:
    """Draft controls update coordinator-local state without network calls."""
    coordinator = _coordinator()
    entry = _entry(coordinator)
    duration = MonocleOverrideMinutesNumber(coordinator, entry)
    mode = MonocleOverrideModeSelect(coordinator, entry)

    assert duration.native_value == 60.0
    assert duration.entity_category is EntityCategory.CONFIG
    await duration.async_set_native_value(90)
    assert coordinator.selected_override_minutes == 90

    assert mode.current_option == "None"
    await mode.async_select_option("On")
    assert coordinator.selected_override_mode == "On"
    assert coordinator.async_update_listeners.call_count == 2


async def test_button_apply_and_remove_override() -> None:
    """The button applies or removes the current draft override."""
    coordinator = _coordinator(
        connected=True,
        actor_id="actor-1",
        location_id=42,
    )
    entity = MonocleApplyOverrideButton(coordinator, _entry(coordinator))
    assert entity.available is True

    coordinator.selected_override_mode = "On"
    coordinator.selected_override_minutes = 120
    await entity.async_press()
    coordinator.client.async_save_override.assert_awaited_once_with(
        actor_id="actor-1",
        location_id=42,
        mode="on",
        valid_until=120,
    )

    coordinator.selected_override_mode = "None"
    await entity.async_press()
    coordinator.client.async_remove_override.assert_awaited_once_with(
        actor_id="actor-1",
        location_id=42,
    )


async def test_button_reports_unavailable_and_api_failure() -> None:
    """Action failures are exposed to Home Assistant rather than swallowed."""
    coordinator = _coordinator(connected=False)
    entity = MonocleApplyOverrideButton(coordinator, _entry(coordinator))
    assert entity.available is False
    with pytest.raises(HomeAssistantError):
        await entity.async_press()

    coordinator.client.state = MonocleState(
        connected=True,
        actor_id="actor-1",
        location_id=42,
    )
    coordinator.selected_override_mode = "Off"
    coordinator.client.async_save_override.side_effect = MonocleClientError("failed")
    with pytest.raises(HomeAssistantError):
        await entity.async_press()


def test_normalize_on_off_edge_cases() -> None:
    """Display normalization handles absent and non-standard API values."""
    from custom_components.ha_monocle_cloud_status.entity import normalize_on_off

    assert normalize_on_off(None) == "None"
    assert normalize_on_off(None, none_as="Unknown") == "Unknown"
    assert normalize_on_off("unexpected") == "unexpected"
