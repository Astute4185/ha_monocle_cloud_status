"""Socket.IO streaming client for Monocle Cloud Status."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone

import aiohttp
import socketio

from .auth import MonocleAuthSession
from .const import (
    ORIGIN,
    REMOVE_OVERRIDE_URL,
    SAVE_OVERRIDE_URL,
    SOCKET_BASE_URL,
)

_LOGGER = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class MonocleClientError(Exception):
    """Raised when the Monocle socket client fails."""


@dataclass(slots=True)
class MonocleState:
    """Latest pushed telemetry from the websocket."""

    connected: bool = False
    socket_sid: str | None = None
    latest_event: dict[str, Any] | None = None
    mains_pwr: float | None = None
    solar_pwr: float | None = None
    house_pwr: float | None = None
    battery_pwr: float | None = None
    device_online: bool | None = None
    load_state: str | None = None
    actor_id: str | None = None
    location_id: int | None = None
    override_mode: str = "None"
    override_valid_until: datetime | None = None
    raw_phydev: list[dict[str, Any]] = field(default_factory=list)
    raw_channels: list[dict[str, Any]] = field(default_factory=list)


class MonocleSocketClient:
    """Socket.IO client for Monocle telemetry and override control."""

    def __init__(
        self,
        auth: MonocleAuthSession,
        *,
        event_callback: EventCallback | None = None,
    ) -> None:
        self._auth = auth
        self._event_callback = event_callback
        self.state = MonocleState()

        self._sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=2,
            reconnection_delay_max=30,
            logger=False,
            engineio_logger=False,
        )

        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._sio.event
        async def connect() -> None:
            _LOGGER.info("Socket connected")
            self.state.connected = True
            self.state.socket_sid = self._sio.sid

        @self._sio.event
        async def disconnect() -> None:
            _LOGGER.warning("Socket disconnected")
            self.state.connected = False
            self.state.socket_sid = None

        @self._sio.on("event")
        async def on_event(data: dict[str, Any]) -> None:
            self._handle_event(data)

            if self._event_callback is not None:
                result = self._event_callback(data)
                if asyncio.iscoroutine(result):
                    await result

        @self._sio.event
        async def connect_error(data: Any) -> None:
            _LOGGER.error("Socket connect error: %r", data)

    async def async_connect(self) -> None:
        """Connect to the Monocle Socket.IO endpoint."""
        try:
            await self._sio.connect(
                SOCKET_BASE_URL,
                transports=["websocket"],
                headers={"Origin": ORIGIN},
                auth={
                    "token": self._auth.access_token,
                    "locationId": self._auth.location_id,
                },
                wait_timeout=20,
            )
        except Exception as err:
            raise MonocleClientError(f"Failed to connect socket: {err}") from err

    async def async_disconnect(self) -> None:
        """Disconnect from the Monocle Socket.IO endpoint."""
        if self._sio.connected:
            await self._sio.disconnect()

    async def async_wait_forever(self) -> None:
        """Block and keep the client alive."""
        await self._sio.wait()

    async def async_save_override(
        self,
        *,
        actor_id: str,
        location_id: int,
        mode: str,
        valid_until: int,
    ) -> None:
        """Save an override for a controllable actor."""
        if mode not in {"on", "off"}:
            raise MonocleClientError(f"Invalid override mode: {mode}")

        headers = {
            "Authorization": f"Token {self._auth.access_token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "Referer": f"{ORIGIN}/",
            "X-Requested-With": "au.com.catchpower.monocle",
        }

        payload = {
            "actorID": actor_id,
            "locationId": location_id,
            "override": {
                "validUntil": int(valid_until),
                "mode": mode,
            },
        }

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                SAVE_OVERRIDE_URL,
                json=payload,
                headers=headers,
            ) as resp:
                raw = await resp.text()
                if not 200 <= resp.status < 300:
                    raise MonocleClientError(
                        f"Failed to save override: HTTP {resp.status}: {raw[:500]}"
                    )

    async def async_remove_override(
        self,
        *,
        actor_id: str,
        location_id: int,
    ) -> None:
        """Remove an override for a controllable actor."""
        headers = {
            "Authorization": f"Token {self._auth.access_token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "Referer": f"{ORIGIN}/",
            "X-Requested-With": "au.com.catchpower.monocle",
        }

        payload = {
            "actorID": actor_id,
            "locationId": location_id,
        }

        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                REMOVE_OVERRIDE_URL,
                json=payload,
                headers=headers,
            ) as resp:
                raw = await resp.text()
                if not 200 <= resp.status < 300:
                    raise MonocleClientError(
                        f"Failed to remove override: HTTP {resp.status}: {raw[:500]}"
                    )

    def _handle_event(self, data: dict[str, Any]) -> None:
        self.state.latest_event = data
        self.state.mains_pwr = _safe_float(data.get("mainsPWR"))
        self.state.solar_pwr = _safe_float(data.get("solarPWR"))
        self.state.house_pwr = _safe_float(data.get("housePWR"))
        self.state.battery_pwr = _safe_float(data.get("batteryPWR"))
    
        phydev = data.get("phyDev") or []
        channels = data.get("channels") or []
        controllable = data.get("controllable") or {}
        other = controllable.get("OTHER") or []
    
        self.state.raw_phydev = phydev if isinstance(phydev, list) else []
        self.state.raw_channels = channels if isinstance(channels, list) else []
    
        self.state.device_online = self._extract_device_online(self.state.raw_phydev)
        self.state.load_state = self._extract_load_state(other)   # ✅ FIXED
        self.state.actor_id = self._extract_actor_id(other)
        self.state.override_mode = self._extract_override_mode(other)
        self.state.override_valid_until = self._extract_override_valid_until(other)
        self.state.location_id = self._safe_location_id()

    def _safe_location_id(self) -> int | None:
        try:
            return int(self._auth.location_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_device_online(phydev: list[dict[str, Any]]) -> bool | None:
        for device in phydev:
            online = device.get("online")
            if isinstance(online, bool):
                return online
        return None

    @staticmethod
    def _extract_actor_id(other: list[dict[str, Any]]) -> str | None:
        for item in other:
            actor_id = item.get("id")
            if actor_id is not None:
                return str(actor_id)
        return None

    @staticmethod
    def _extract_load_state(other: list[dict[str, Any]]) -> str | None:
        for item in other:
            if "state" not in item:
                continue
    
            value = item.get("state")
            if value is None:
                return None
    
            value = str(value).strip().lower()
            if value in {"on", "off"}:
                return value
    
            return value
    
        return None

    @staticmethod
    def _extract_override_mode(other: list[dict[str, Any]]) -> str | None:
        for item in other:
            override = item.get("override") or {}
            fields = override.get("fields") or []
    
            for field in fields:
                if field.get("id") != "mode":
                    continue
    
                value = field.get("currentValue")
                if value is None:
                    return None
    
                value = str(value).strip().lower()
                if value in {"on", "off"}:
                    return value
    
                return value
    
        return None

    @staticmethod
    def _extract_override_valid_until(other: list[dict[str, Any]]) -> datetime | None:
        for item in other:
            override = item.get("override") or {}
            fields = override.get("fields") or []
            for field in fields:
                if field.get("id") == "validUntil":
                    value = field.get("currentValue")
                    if value is None:
                        return None
    
                    try:
                        # websocket appears to provide epoch milliseconds
                        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
                    except (TypeError, ValueError, OSError):
                        return None
    
        return None


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
