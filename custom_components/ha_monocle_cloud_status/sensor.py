"""Sensor platform for Monocle Cloud Status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import MonocleCoordinator
from .entity import MonocleBaseEntity, normalize_on_off


@dataclass(frozen=True, kw_only=True)
class MonocleSensorDescription(SensorEntityDescription):
    value_fn: Callable[[MonocleCoordinator], float | str | datetime | None]


SENSORS: tuple[MonocleSensorDescription, ...] = (
    MonocleSensorDescription(
        key="mains_power",
        translation_key="mains_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.client.state.mains_pwr,
    ),
    MonocleSensorDescription(
        key="solar_power",
        translation_key="solar_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.client.state.solar_pwr,
    ),
    MonocleSensorDescription(
        key="house_power",
        translation_key="house_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.client.state.house_pwr,
    ),
    MonocleSensorDescription(
        key="battery_power",
        translation_key="battery_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda c: c.client.state.battery_pwr,
    ),
    MonocleSensorDescription(
        key="load_state",
        translation_key="load_state",
        value_fn=lambda c: normalize_on_off(
            c.client.state.load_state,
            none_as="Unknown",
        ),
    ),
    MonocleSensorDescription(
        key="override_mode",
        translation_key="override_mode",
        value_fn=lambda c: normalize_on_off(
            c.client.state.override_mode,
            none_as="None",
        ),
    ),
    MonocleSensorDescription(
        key="override_valid_until",
        translation_key="override_valid_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda c: c.client.state.override_valid_until,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Monocle sensors."""
    coordinator: MonocleCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities = [MonocleSensor(coordinator, entry, description) for description in SENSORS]
    async_add_entities(entities)


class MonocleSensor(MonocleBaseEntity, SensorEntity):
    """Representation of a Monocle sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MonocleCoordinator,
        entry: ConfigEntry,
        description: MonocleSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.key.replace("_", " ")

    @property
    def native_value(self) -> float | str | datetime | None:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def available(self) -> bool:
        return self.coordinator.client.state.connected
