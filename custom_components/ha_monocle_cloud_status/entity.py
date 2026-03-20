"""Shared entity classes for Monocle Cloud Status."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .coordinator import MonocleCoordinator
from typing import Any


class MonocleBaseEntity(CoordinatorEntity[MonocleCoordinator]):
    """Base entity for Monocle Cloud Status."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        location_id = self.coordinator.location_id
        return DeviceInfo(
            identifiers={(DOMAIN, location_id)},
            name=f"Monocle {location_id}",
            manufacturer="Catch Power",
            model="Monocle",
        )

def normalize_on_off(value: Any, *, none_as: str = "None") -> str:
    if value is None:
        return none_as

    value = str(value).strip().lower()

    if value == "on":
        return "On"
    if value == "off":
        return "Off"

    return str(value)


def format_timestamp(ts: int | None) -> str:
    if ts is None:
        return "None"

    try:
        dt = dt_util.as_local(dt_util.utc_from_timestamp(ts / 1000))
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "Unknown"
