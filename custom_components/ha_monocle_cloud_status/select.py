"""Select platform for Monocle Cloud Status."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MonocleConfigEntry
from .coordinator import MonocleCoordinator
from .entity import MonocleBaseEntity

OVERRIDE_OPTIONS = ["On", "Off", "None"]


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MonocleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Monocle select entities."""
    async_add_entities(
        [MonocleOverrideModeSelect(entry.runtime_data.coordinator, entry)]
    )


class MonocleOverrideModeSelect(MonocleBaseEntity, SelectEntity):
    """Select an override mode to apply."""

    _attr_translation_key = "hot_water_override_mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = OVERRIDE_OPTIONS

    def __init__(
        self, coordinator: MonocleCoordinator, entry: MonocleConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_hot_water_override_mode"

    @property
    def current_option(self) -> str | None:
        """Return the selected draft override mode."""
        return self.coordinator.selected_override_mode

    async def async_select_option(self, option: str) -> None:
        """Update the draft override mode."""
        self.coordinator.selected_override_mode = option
        self.coordinator.async_update_listeners()
