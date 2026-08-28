"""Button platform for Monocle Cloud Status."""

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MonocleConfigEntry
from .client import MonocleClientError
from .const import DOMAIN
from .coordinator import MonocleCoordinator
from .entity import MonocleBaseEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MonocleConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Monocle button entities."""
    async_add_entities(
        [MonocleApplyOverrideButton(entry.runtime_data.coordinator, entry)]
    )


class MonocleApplyOverrideButton(MonocleBaseEntity, ButtonEntity):
    """Apply the current draft hot-water override."""

    _attr_translation_key = "apply_hot_water_override"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: MonocleCoordinator, entry: MonocleConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_apply_hot_water_override"

    @property
    def available(self) -> bool:
        """Return whether an override can be applied."""
        state = self.coordinator.client.state
        return (
            state.connected
            and state.actor_id is not None
            and state.location_id is not None
        )

    async def async_press(self) -> None:
        """Apply the selected override."""
        state = self.coordinator.client.state
        if not state.connected or state.actor_id is None or state.location_id is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="override_unavailable",
            )

        try:
            mode = self.coordinator.selected_override_mode
            if mode == "None":
                await self.coordinator.client.async_remove_override(
                    actor_id=state.actor_id,
                    location_id=state.location_id,
                )
                return

            await self.coordinator.client.async_save_override(
                actor_id=state.actor_id,
                location_id=state.location_id,
                mode="on" if mode == "On" else "off",
                valid_until=self.coordinator.selected_override_minutes,
            )
        except MonocleClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="override_failed",
            ) from err
