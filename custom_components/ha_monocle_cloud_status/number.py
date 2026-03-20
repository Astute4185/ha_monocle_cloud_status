"""Number platform for Monocle Cloud Status."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import MonocleCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MonocleCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([MonocleOverrideMinutesNumber(coordinator, entry)])


class MonocleOverrideMinutesNumber(CoordinatorEntity[MonocleCoordinator], NumberEntity):
    """Override duration number."""

    _attr_has_entity_name = True
    _attr_translation_key = "hot_water_override_minutes"
    _attr_native_min_value = 1
    _attr_native_max_value = 480
    _attr_native_step = 1
    _attr_mode = "box"

    def __init__(self, coordinator: MonocleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_hot_water_override_minutes"

    @property
    def device_info(self) -> DeviceInfo:
        location_id = self.coordinator.location_id
        return DeviceInfo(
            identifiers={(DOMAIN, str(location_id))},
            name=f"Monocle {location_id}",
            manufacturer="Catch Power",
            model="Monocle",
        )

    @property
    def native_value(self) -> float:
        return float(self.coordinator.selected_override_minutes)

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.selected_override_minutes = int(value)
        self.coordinator.async_update_listeners()
