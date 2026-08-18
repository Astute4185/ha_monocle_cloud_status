"""Coordinator for Monocle Cloud Status."""

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .auth import MonocleAuthSession
from .client import MonocleSocketClient

_LOGGER = logging.getLogger(__name__)


class MonocleCoordinator(DataUpdateCoordinator[dict | None]):
    """Push coordinator for Monocle telemetry."""

    client: MonocleSocketClient
    location_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        auth: MonocleAuthSession,
        websession: aiohttp.ClientSession,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Monocle Cloud Status",
        )
        self.client = MonocleSocketClient(
            auth,
            websession,
            event_callback=self._async_on_event,
        )
        self.location_id = str(auth.location_id)
        self.selected_override_mode = "None"
        self.selected_override_minutes = 60

    async def async_start(self) -> None:
        """Start the socket connection."""
        await self.client.async_connect()
        self.async_set_updated_data(self.client.state.latest_event)

    async def async_stop(self) -> None:
        """Stop the socket connection."""
        await self.client.async_disconnect()

    @callback
    def _async_on_event(self, _: dict) -> None:
        """Handle pushed event data."""
        self.async_set_updated_data(self.client.state.latest_event)
