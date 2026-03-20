"""Button platform for Monocle Cloud Status."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([MonocleApplyOverrideButton(coordinator, entry)])


class MonocleApplyOverrideButton(CoordinatorEntity[MonocleCoordinator], ButtonEntity):
    """Apply override button."""

    _attr_has_entity_name = True
    _attr_translation_key = "apply_hot_water_override"

    def __init__(self, coordinator: MonocleCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_apply_hot_water_override"

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
    def available(self) -> bool:
        state = self.coordinator.client.state
        return (
            state.connected
            and state.actor_id is not None
            and state.location_id is not None
        )

    async def async_press(self) -> None:
        state = self.coordinator.client.state
        mode = self.coordinator.selected_override_mode
        minutes = self.coordinator.selected_override_minutes

        if mode == "None":
            await self.coordinator.client.async_remove_override(
                actor_id=state.actor_id,
                location_id=state.location_id,
            )
            return

        api_mode = "on" if mode == "On" else "off"

        await self.coordinator.client.async_save_override(
            actor_id=state.actor_id,
            location_id=state.location_id,
            mode=api_mode,
            valid_until=minutes,
        )
