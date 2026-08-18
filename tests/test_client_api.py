"""Unit tests for Monocle client API operations."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from custom_components.ha_monocle_cloud_status.auth import MonocleAuthSession
from custom_components.ha_monocle_cloud_status.client import (
    MonocleClientError,
    MonocleSocketClient,
    MonocleState,
)
from custom_components.ha_monocle_cloud_status.const import (
    REMOVE_OVERRIDE_URL,
    SAVE_OVERRIDE_URL,
)
import pytest
import socketio

AUTH = MonocleAuthSession(
    access_token="token",
    location_id="42",
    token_expiry_ms=None,
    user_id=None,
    email=None,
    display_name=None,
)


def _client() -> MonocleSocketClient:
    client = object.__new__(MonocleSocketClient)
    client._auth = AUTH
    client.state = MonocleState()
    client._availability_lost = False
    return client


def _websession(*, status: int = 200, text: str = "ok") -> MagicMock:
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.post.return_value = context
    return session


async def test_connect_and_disconnect() -> None:
    """Socket connect/disconnect delegates to python-socketio."""
    client = _client()
    sio = MagicMock()
    sio.connect = AsyncMock()
    sio.connected = True
    sio.disconnect = AsyncMock()
    client._sio = sio

    await client.async_connect()
    sio.connect.assert_awaited_once()

    await client.async_disconnect()
    sio.disconnect.assert_awaited_once()


async def test_disconnect_when_already_disconnected() -> None:
    """Disconnect is a no-op when the socket is already down."""
    client = _client()
    sio = MagicMock()
    sio.connected = False
    sio.disconnect = AsyncMock()
    client._sio = sio
    await client.async_disconnect()
    sio.disconnect.assert_not_awaited()


async def test_connect_error_is_normalized() -> None:
    """Socket.IO failures become the integration client exception."""
    client = _client()
    sio = MagicMock()
    sio.connect = AsyncMock(side_effect=socketio.exceptions.ConnectionError())
    client._sio = sio
    with pytest.raises(MonocleClientError, match="socket"):
        await client.async_connect()


async def test_save_and_remove_override() -> None:
    """Override operations build the expected API payloads."""
    client = _client()
    client._async_post = AsyncMock()

    await client.async_save_override(
        actor_id="actor-1",
        location_id=42,
        mode="on",
        valid_until=60,
    )
    client._async_post.assert_awaited_with(
        SAVE_OVERRIDE_URL,
        {
            "actorID": "actor-1",
            "locationId": 42,
            "override": {"validUntil": 60, "mode": "on"},
        },
    )

    await client.async_remove_override(actor_id="actor-1", location_id=42)
    client._async_post.assert_awaited_with(
        REMOVE_OVERRIDE_URL,
        {"actorID": "actor-1", "locationId": 42},
    )


async def test_save_override_rejects_invalid_mode() -> None:
    """Only API-supported override modes are accepted."""
    client = _client()
    with pytest.raises(MonocleClientError, match="Invalid override mode"):
        await client.async_save_override(
            actor_id="actor-1",
            location_id=42,
            mode="invalid",
            valid_until=60,
        )


async def test_post_success_and_http_failure() -> None:
    """Authenticated API POSTs handle successful and failed HTTP responses."""
    client = _client()
    client._websession = _websession(status=200)
    await client._async_post("https://example.test", {"value": 1})
    client._websession.post.assert_called_once()

    client._websession = _websession(status=500, text="failed")
    with pytest.raises(MonocleClientError, match="HTTP 500"):
        await client._async_post("https://example.test", {"value": 1})


async def test_post_transport_failure() -> None:
    """aiohttp failures are normalized for action handlers."""
    client = _client()
    session = MagicMock()
    session.post.side_effect = aiohttp.ClientError("offline")
    client._websession = session
    with pytest.raises(MonocleClientError, match="communicate"):
        await client._async_post("https://example.test", {})


class _FakeSocketIO:
    """Minimal decorator-compatible Socket.IO client for callback tests."""

    def __init__(self) -> None:
        self.handlers = {}
        self.sid = "socket-id"
        self.connected = False

    def event(self, handler):
        self.handlers[handler.__name__] = handler
        return handler

    def on(self, name):
        def decorator(handler):
            self.handlers[name] = handler
            return handler

        return decorator


async def test_socket_callbacks_update_state_and_notify() -> None:
    """Registered Socket.IO callbacks drive availability and telemetry state."""
    sio = _FakeSocketIO()
    callback = AsyncMock()
    websession = MagicMock()
    with patch(
        "custom_components.ha_monocle_cloud_status.client.socketio.AsyncClient",
        return_value=sio,
    ):
        client = MonocleSocketClient(AUTH, websession, event_callback=callback)

    await sio.handlers["connect"]()
    assert client.state.connected is True
    assert client.state.socket_sid == "socket-id"

    callback.assert_not_awaited()

    await sio.handlers["event"]({"mainsPWR": 12})
    assert client.state.mains_pwr == 12.0
    callback.assert_awaited_once_with({"mainsPWR": 12})

    callback.reset_mock()
    await sio.handlers["disconnect"]("transport error")
    assert client.state.connected is False
    assert client._availability_lost is True
    callback.assert_awaited_once_with({"mainsPWR": 12})

    callback.reset_mock()
    await sio.handlers["connect"]()
    assert client._availability_lost is False
    callback.assert_awaited_once_with({"mainsPWR": 12})
    await sio.handlers["connect_error"]("temporary")
