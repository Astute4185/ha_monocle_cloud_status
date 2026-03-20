"""The Monocle Cloud Status integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .auth import async_login
from .const import CONF_PASSWORD, CONF_USERNAME, DATA_COORDINATOR, DOMAIN, PLATFORMS
from .coordinator import MonocleCoordinator

type MonocleConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: MonocleConfigEntry) -> bool:
    """Set up Monocle Cloud Status from a config entry."""
    auth = await async_login(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinator = MonocleCoordinator(hass, auth)
    await coordinator.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonocleConfigEntry) -> bool:
    """Unload a config entry."""
    entry_data = hass.data[DOMAIN].pop(entry.entry_id)
    coordinator: MonocleCoordinator = entry_data[DATA_COORDINATOR]

    await coordinator.async_stop()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok