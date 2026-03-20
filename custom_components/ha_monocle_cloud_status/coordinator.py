"""Coordinator for Monocle Cloud Status."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .auth import MonocleAuthSession
from .client import MonocleSocketClient

_LOGGER = logging.getLogger(__name__)


class MonocleCoordinator(DataUpdateCoordinator[dict | None]):
    """Push coordinator for Monocle telemetry."""

    def __init__(self, hass: HomeAssistant, auth: MonocleAuthSession) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Monocle Cloud Status",
        )
        self.client = MonocleSocketClient(auth, event_callback=self._async_on_event)
        self._wait_task: asyncio.Task | None = None

        self.location_id = str(auth.location_id)

        # Draft UI values only
        self.selected_override_mode: str = "None"
        self.selected_override_minutes: int = 60

    async def async_start(self) -> None:
        """Start the socket connection."""
        await self.client.async_connect()
        self.async_set_updated_data(self.client.state.latest_event)

        if self._wait_task is None:
            self._wait_task = self.hass.async_create_background_task(
                self.client.async_wait_forever(),
                "monocle_socket_wait",
            )

    async def async_stop(self) -> None:
        """Stop the socket connection."""
        if self._wait_task:
            self._wait_task.cancel()
            self._wait_task = None

        await self.client.async_disconnect()

    @callback
    def _async_on_event(self, _: dict) -> None:
        """Handle pushed event data."""
        self.async_set_updated_data(self.client.state.latest_event)
