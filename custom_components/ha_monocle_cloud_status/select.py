"""Select platform for Monocle Cloud Status."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import MonocleCoordinator

OVERRIDE_OPTIONS = ["On", "Off", "None"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MonocleCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([MonocleOverrideModeSelect(coordinator, entry)])


class MonocleOverrideModeSelect(CoordinatorEntity[MonocleCoordinator], SelectEntity):
    """Override mode selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "hot_water_override_mode"
    _attr_options = OVERRIDE_OPTIONS

    def __init__(self, coordinator: MonocleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_hot_water_override_mode"

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
    def current_option(self) -> str | None:
        return self.coordinator.selected_override_mode

    async def async_select_option(self, option: str) -> None:
        self.coordinator.selected_override_mode = option
        self.coordinator.async_update_listeners()
