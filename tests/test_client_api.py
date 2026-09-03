"""Unit tests for Monocle client API operations."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from custom_components.ha_monocle_cloud_status.auth import (
    MonocleAuthManager,
    MonocleAuthSession,
    MonocleInvalidAuthError,
)
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


def _auth_manager() -> MagicMock:
    manager = MagicMock(spec=MonocleAuthManager)
    manager.location_id = AUTH.location_id
    manager.socket_auth = MagicMock(
        return_value={"token": AUTH.access_token, "locationId": AUTH.location_id}
    )
    manager.async_refresh_if_needed = AsyncMock(return_value=AUTH)
    manager.async_refresh_after_rejection = AsyncMock(return_value=AUTH)
    manager.request_reauth = MagicMock()
    return manager


def _client() -> MonocleSocketClient:
    client = object.__new__(MonocleSocketClient)
    client._auth_manager = _auth_manager()
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
    """Socket connect and shutdown delegate to python-socketio."""
    client = _client()
    sio = MagicMock()
    sio.connect = AsyncMock()
    sio.shutdown = AsyncMock()
    client._sio = sio

    await client.async_connect()
    sio.connect.assert_awaited_once()
    assert sio.connect.await_args.kwargs["auth"] is client._auth_manager.socket_auth

    await client.async_disconnect()
    sio.shutdown.assert_awaited_once_with()


async def test_disconnect_shuts_down_while_socket_is_disconnected() -> None:
    """Shutdown is called even when Socket.IO is between reconnect attempts."""
    client = _client()
    sio = MagicMock()
    sio.connected = False
    sio.shutdown = AsyncMock()
    client._sio = sio

    await client.async_disconnect()

    sio.shutdown.assert_awaited_once_with()


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


async def test_post_refreshes_and_retries_after_unauthorized() -> None:
    """A rejected API token is refreshed and the request is retried once."""
    client = _client()
    refreshed = MonocleAuthSession(
        access_token="new-token",
        location_id="42",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )
    client._auth_manager.async_refresh_after_rejection.return_value = refreshed
    client._async_post_once = AsyncMock(side_effect=[(401, "expired"), (200, "ok")])

    await client._async_post("https://example.test", {"value": 1})

    client._auth_manager.async_refresh_after_rejection.assert_awaited_once_with(
        AUTH.access_token
    )
    assert client._async_post_once.await_count == 2
    assert (
        client._async_post_once.await_args_list[1].kwargs["access_token"] == "new-token"
    )


async def test_post_second_auth_rejection_requests_reauth() -> None:
    """A second 401/403 after refresh requests Home Assistant reauthentication."""
    client = _client()
    client._async_post_once = AsyncMock(
        side_effect=[(401, "expired"), (403, "rejected")]
    )

    with pytest.raises(MonocleClientError, match="authentication was rejected"):
        await client._async_post("https://example.test", {})

    client._auth_manager.request_reauth.assert_called_once_with()


async def test_post_invalid_refresh_is_normalized() -> None:
    """Invalid stored credentials become a client error after reauth is requested."""
    client = _client()
    client._async_post_once = AsyncMock(return_value=(401, "expired"))
    client._auth_manager.async_refresh_after_rejection.side_effect = (
        MonocleInvalidAuthError()
    )

    with pytest.raises(MonocleClientError, match="credentials"):
        await client._async_post("https://example.test", {})


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
        client = MonocleSocketClient(
            _auth_manager(),
            websession,
            event_callback=callback,
        )

    await sio.handlers["connect"]()
    assert client.state.connected is True
    assert client.state.telemetry_fresh is False
    assert client.state.socket_sid == "socket-id"

    callback.assert_not_awaited()

    await sio.handlers["event"]({"mainsPWR": 12})
    assert client.state.mains_pwr == 12.0
    assert client.state.telemetry_fresh is True
    assert client.state.last_event_at is not None
    first_event_at = client.state.last_event_at
    callback.assert_awaited_once_with({"mainsPWR": 12})

    callback.reset_mock()
    await sio.handlers["disconnect"]("transport error")
    assert client.state.connected is False
    assert client.state.telemetry_fresh is False
    assert client.state.last_event_at == first_event_at
    assert client._availability_lost is True
    callback.assert_awaited_once_with({"mainsPWR": 12})

    callback.reset_mock()
    await sio.handlers["connect"]()
    assert client.state.connected is True
    assert client.state.telemetry_fresh is False
    assert client.state.last_event_at == first_event_at
    assert client._availability_lost is False
    callback.assert_awaited_once_with({"mainsPWR": 12})

    callback.reset_mock()
    await sio.handlers["event"]({"mainsPWR": 13})
    assert client.state.telemetry_fresh is True
    assert client.state.mains_pwr == 13.0
    assert client.state.last_event_at is not None
    assert client.state.last_event_at >= first_event_at
    callback.assert_awaited_once_with({"mainsPWR": 13})

    await sio.handlers["connect_error"]("temporary")
