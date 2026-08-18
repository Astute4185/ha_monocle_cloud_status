"""The Monocle Cloud Status integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import MonocleConnectionError, MonocleInvalidAuthError, async_login
from .client import MonocleClientError
from .const import CONF_PASSWORD, CONF_USERNAME, PLATFORMS
from .coordinator import MonocleCoordinator


@dataclass(slots=True)
class MonocleRuntimeData:
    """Runtime data stored on the config entry."""

    coordinator: MonocleCoordinator


type MonocleConfigEntry = ConfigEntry[MonocleRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: MonocleConfigEntry) -> bool:
    """Set up Monocle Cloud Status from a config entry."""
    websession = async_get_clientsession(hass)
    try:
        auth = await async_login(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=websession,
        )
    except MonocleInvalidAuthError as err:
        raise ConfigEntryAuthFailed("Invalid Monocle credentials") from err
    except MonocleConnectionError as err:
        raise ConfigEntryNotReady("Unable to authenticate with Monocle") from err

    coordinator = MonocleCoordinator(hass, entry, auth, websession)
    try:
        await coordinator.async_start()
    except MonocleClientError as err:
        raise ConfigEntryNotReady("Unable to connect to Monocle") from err

    entry.runtime_data = MonocleRuntimeData(coordinator=coordinator)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await coordinator.async_stop()
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MonocleConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.coordinator.async_stop()
    return True
