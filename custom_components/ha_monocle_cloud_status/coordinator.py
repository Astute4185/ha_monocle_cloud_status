"""Coordinator for Monocle Cloud Status."""

import asyncio
from contextlib import suppress
import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .auth import MonocleAuthManager
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
        auth_manager: MonocleAuthManager,
        websession: aiohttp.ClientSession,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Monocle Cloud Status",
        )
        self._entry = entry
        self._auth_manager = auth_manager
        self._auth_refresh_task: asyncio.Task[None] | None = None
        self.client = MonocleSocketClient(
            auth_manager,
            websession,
            event_callback=self._async_on_event,
        )
        self.location_id = str(auth_manager.location_id)
        self.selected_override_mode = "None"
        self.selected_override_minutes = 60

    async def async_start(self) -> None:
        """Start the socket connection and token refresh loop."""
        await self.client.async_connect()
        self._auth_refresh_task = self._entry.async_create_background_task(
            self.hass,
            self._auth_manager.async_refresh_loop(),
            "Monocle authentication refresh",
        )
        self.async_set_updated_data(self.client.state.latest_event)

    async def async_stop(self) -> None:
        """Stop authentication refresh and the socket connection."""
        if self._auth_refresh_task is not None:
            self._auth_refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._auth_refresh_task
            self._auth_refresh_task = None
        await self.client.async_disconnect()

    @callback
    def _async_on_event(self, _: dict) -> None:
        """Handle pushed event data."""
        self.async_set_updated_data(self.client.state.latest_event)
