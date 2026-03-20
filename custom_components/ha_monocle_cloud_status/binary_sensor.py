"""Binary sensor platform for Monocle Cloud Status."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import MonocleCoordinator
from .entity import MonocleBaseEntity



async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Monocle binary sensors."""
    coordinator: MonocleCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([MonocleOnlineBinarySensor(coordinator, entry)])


class MonocleOnlineBinarySensor(MonocleBaseEntity, BinarySensorEntity):
    """Online status binary sensor."""

    _attr_has_entity_name = True
    _attr_name = "device online"

    def __init__(self, coordinator: MonocleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_device_online"

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.client.state.device_online

    @property
    def available(self) -> bool:
        return self.coordinator.client.state.connected
