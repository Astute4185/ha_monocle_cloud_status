"""Stable compatibility surface for companion Monocle integrations."""

from dataclasses import dataclass

from homeassistant.core import HomeAssistant

from . import MonocleConfigEntry
from .const import DOMAIN
from .coordinator import MonocleCoordinator


@dataclass(frozen=True, slots=True)
class MonocleExtensionState:
    """State intentionally exposed to companion integrations."""

    connected: bool
    actor_id: str | None
    location_id: int | None


def get_parent_coordinator(
    hass: HomeAssistant, entry_id: str
) -> MonocleCoordinator | None:
    """Return a configured Monocle coordinator for a companion integration."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        return None
    if getattr(entry, "runtime_data", None) is None:
        return None
    typed_entry: MonocleConfigEntry = entry
    return typed_entry.runtime_data.coordinator


def get_extension_state(coordinator: MonocleCoordinator) -> MonocleExtensionState:
    """Return the supported companion-integration state contract."""
    state = coordinator.client.state
    return MonocleExtensionState(
        connected=state.connected,
        actor_id=state.actor_id,
        location_id=state.location_id,
    )
