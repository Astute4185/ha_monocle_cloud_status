"""Socket.IO streaming client for Monocle Cloud Status."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any

import aiohttp
import socketio

from .auth import MonocleAuthSession
from .const import ORIGIN, REMOVE_OVERRIDE_URL, SAVE_OVERRIDE_URL, SOCKET_BASE_URL

_LOGGER = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


class MonocleClientError(Exception):
    """Raised when communication with Monocle fails."""


@dataclass(slots=True)
class MonocleState:
    """Latest pushed telemetry from the Monocle websocket."""

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
    override_mode: str | None = None
    override_valid_until: datetime | None = None
    raw_phydev: list[dict[str, Any]] = field(default_factory=list)
    raw_channels: list[dict[str, Any]] = field(default_factory=list)


class MonocleSocketClient:
    """Socket.IO client for Monocle telemetry and override control."""

    def __init__(
        self,
        auth: MonocleAuthSession,
        websession: aiohttp.ClientSession,
        *,
        event_callback: EventCallback | None = None,
    ) -> None:
        self._auth = auth
        self._websession = websession
        self._event_callback = event_callback
        self.state = MonocleState()
        self._availability_lost = False
        self._sio = socketio.AsyncClient(
            http_session=websession,
            reconnection=True,
            reconnection_attempts=0,
            reconnection_delay=2,
            reconnection_delay_max=30,
            logger=False,
            engineio_logger=False,
        )
        self._register_handlers()

    def _register_handlers(self) -> None:
        """Register Socket.IO callbacks."""

        @self._sio.event
        async def connect() -> None:
            recovered = self._availability_lost
            if recovered:
                _LOGGER.info("Monocle connection recovered")
                self._availability_lost = False
            else:
                _LOGGER.debug("Monocle socket connected")
            self.state.connected = True
            self.state.socket_sid = self._sio.sid
            if recovered:
                await self._async_notify(self.state.latest_event or {})

        @self._sio.event
        async def disconnect(reason: Any = None) -> None:
            if self.state.connected:
                _LOGGER.info("Monocle connection unavailable")
                _LOGGER.debug("Monocle socket disconnect reason: %r", reason)
                self._availability_lost = True
            self.state.connected = False
            self.state.socket_sid = None
            await self._async_notify(self.state.latest_event or {})

        @self._sio.on("event")
        async def on_event(data: dict[str, Any]) -> None:
            self._handle_event(data)
            await self._async_notify(data)

        @self._sio.event
        async def connect_error(data: Any) -> None:
            _LOGGER.debug("Monocle socket connection error: %r", data)

    async def _async_notify(self, data: dict[str, Any]) -> None:
        """Notify Home Assistant that telemetry or availability changed."""
        if self._event_callback is None:
            return
        result = self._event_callback(data)
        if asyncio.iscoroutine(result):
            await result

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
        except (
            socketio.exceptions.ConnectionError,
            aiohttp.ClientError,
            TimeoutError,
        ) as err:
            raise MonocleClientError("Unable to connect to Monocle socket") from err

    async def async_disconnect(self) -> None:
        """Stop the Monocle Socket.IO client and any reconnect attempts."""
        await self._sio.shutdown()

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

        payload = {
            "actorID": actor_id,
            "locationId": location_id,
            "override": {"validUntil": int(valid_until), "mode": mode},
        }
        await self._async_post(SAVE_OVERRIDE_URL, payload)

    async def async_remove_override(self, *, actor_id: str, location_id: int) -> None:
        """Remove an override for a controllable actor."""
        await self._async_post(
            REMOVE_OVERRIDE_URL,
            {"actorID": actor_id, "locationId": location_id},
        )

    async def _async_post(self, url: str, payload: dict[str, Any]) -> None:
        """POST an authenticated Monocle API request."""
        headers = {
            "Authorization": f"Token {self._auth.access_token}",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "Referer": f"{ORIGIN}/",
            "X-Requested-With": "au.com.catchpower.monocle",
        }
        try:
            async with self._websession.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                raw = await response.text()
                if not 200 <= response.status < 300:
                    raise MonocleClientError(
                        f"Monocle request failed with HTTP {response.status}: "
                        f"{raw[:200]}"
                    )
        except MonocleClientError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise MonocleClientError("Unable to communicate with Monocle") from err

    def _handle_event(self, data: dict[str, Any]) -> None:
        """Parse a pushed telemetry event into state."""
        self.state.latest_event = data
        self.state.mains_pwr = _safe_float(data.get("mainsPWR"))
        self.state.solar_pwr = _safe_float(data.get("solarPWR"))
        self.state.house_pwr = _safe_float(data.get("housePWR"))
        self.state.battery_pwr = _safe_float(data.get("batteryPWR"))

        phydev = data.get("phyDev") or []
        channels = data.get("channels") or []
        controllable = data.get("controllable") or {}
        other = (
            (controllable.get("OTHER") or []) if isinstance(controllable, dict) else []
        )

        self.state.raw_phydev = _dict_items(phydev)
        self.state.raw_channels = _dict_items(channels)
        other_items = _dict_items(other)

        self.state.device_online = self._extract_device_online(self.state.raw_phydev)
        self.state.load_state = self._extract_load_state(other_items)
        self.state.actor_id = self._extract_actor_id(other_items)
        self.state.override_mode = self._extract_override_mode(other_items)
        self.state.override_valid_until = self._extract_override_valid_until(
            other_items
        )
        self.state.location_id = self._safe_location_id()

    def _safe_location_id(self) -> int | None:
        try:
            return int(self._auth.location_id)
        except TypeError, ValueError:
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
            if "state" in item:
                return _normalized_lower(item.get("state"))
        return None

    @staticmethod
    def _extract_override_mode(other: list[dict[str, Any]]) -> str | None:
        for item in other:
            override = item.get("override") or {}
            if not isinstance(override, dict):
                continue
            fields = override.get("fields") or []
            if not isinstance(fields, list):
                continue
            for field_data in fields:
                if isinstance(field_data, dict) and field_data.get("id") == "mode":
                    return _normalized_lower(field_data.get("currentValue"))
        return None

    @staticmethod
    def _extract_override_valid_until(other: list[dict[str, Any]]) -> datetime | None:
        for item in other:
            override = item.get("override") or {}
            if not isinstance(override, dict):
                continue
            fields = override.get("fields") or []
            if not isinstance(fields, list):
                continue
            for field_data in fields:
                if (
                    not isinstance(field_data, dict)
                    or field_data.get("id") != "validUntil"
                ):
                    continue
                value = field_data.get("currentValue")
                if value is None:
                    return None
                try:
                    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
                except TypeError, ValueError, OSError:
                    return None
        return None


def _dict_items(value: Any) -> list[dict[str, Any]]:
    """Return dictionary elements from an API list, ignoring foreign values."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _normalized_lower(value: Any) -> str | None:
    """Normalize an optional API value to a lower-case string."""
    if value is None:
        return None
    return str(value).strip().lower()


def _safe_float(value: Any) -> float | None:
    """Convert a value to float if possible."""
    if value is None:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None
