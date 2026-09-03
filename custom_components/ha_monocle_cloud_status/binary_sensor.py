"""Binary sensor platform for Monocle Cloud Status."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MonocleConfigEntry
from .coordinator import MonocleCoordinator
from .entity import MonocleBaseEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MonocleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Monocle binary sensors."""
    async_add_entities(
        [MonocleOnlineBinarySensor(entry.runtime_data.coordinator, entry)]
    )


class MonocleOnlineBinarySensor(MonocleBaseEntity, BinarySensorEntity):
    """Represent the Monocle online state."""

    _attr_translation_key = "device_online"

    def __init__(
        self, coordinator: MonocleCoordinator, entry: MonocleConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_device_online"

    @property
    def is_on(self) -> bool | None:
        """Return whether the Monocle device is online."""
        return self.coordinator.client.state.device_online

    @property
    def available(self) -> bool:
        """Return whether current data is available."""
        state = self.coordinator.client.state
        return state.connected and state.telemetry_fresh
