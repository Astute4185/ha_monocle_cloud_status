"""Shared entity classes for Monocle Cloud Status."""

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MonocleCoordinator


class MonocleBaseEntity(CoordinatorEntity[MonocleCoordinator]):
    """Base entity for Monocle Cloud Status."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        location_id = self.coordinator.location_id
        return DeviceInfo(
            identifiers={(DOMAIN, location_id)},
            name=f"Monocle {location_id}",
            manufacturer="Catch Power",
            model="Monocle",
        )


def normalize_on_off(value: Any, *, none_as: str = "None") -> str:
    """Normalize common on/off values for display."""
    if value is None:
        return none_as
    normalized = str(value).strip().lower()
    if normalized == "on":
        return "On"
    if normalized == "off":
        return "Off"
    return str(value)
