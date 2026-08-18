"""Number platform for Monocle Cloud Status."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
    """Set up Monocle number entities."""
    async_add_entities(
        [MonocleOverrideMinutesNumber(entry.runtime_data.coordinator, entry)]
    )


class MonocleOverrideMinutesNumber(MonocleBaseEntity, NumberEntity):
    """Configure the draft override duration."""

    _attr_translation_key = "hot_water_override_minutes"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 1
    _attr_native_max_value = 480
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: MonocleCoordinator, entry: MonocleConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_hot_water_override_minutes"

    @property
    def native_value(self) -> float:
        """Return the selected draft duration."""
        return float(self.coordinator.selected_override_minutes)

    async def async_set_native_value(self, value: float) -> None:
        """Update the selected draft duration."""
        self.coordinator.selected_override_minutes = int(value)
        self.coordinator.async_update_listeners()
