"""Unit tests for Monocle authentication."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from custom_components.ha_monocle_cloud_status.auth import (
    MonocleAuthManager,
    MonocleAuthSession,
    MonocleConnectionError,
    MonocleInvalidAuthError,
    async_login,
)
import pytest


def _session_with_response(
    *,
    status: int = 200,
    json_data: object | None = None,
    json_error: Exception | None = None,
    text: str = "response",
) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    response.json = AsyncMock(return_value=json_data)
    if json_error is not None:
        response.json.side_effect = json_error

    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock()
    session.post.return_value = context
    return session


async def test_login_success() -> None:
    """A valid login response is normalized into the auth model."""
    session = _session_with_response(
        json_data={
            "accessToken": "token",
            "locationId": 42,
            "tokenExpiryMS": "12345",
            "id": 7,
            "email": "user@example.com",
            "displayName": "User",
        }
    )

    result = await async_login("user@example.com", "secret", session=session)

    assert result.access_token == "token"
    assert result.location_id == "42"
    assert result.token_expiry_ms == 12345
    assert result.user_id == "7"
    assert result.email == "user@example.com"
    assert result.display_name == "User"
    session.post.assert_called_once()


@pytest.mark.parametrize("status", [401, 403])
async def test_login_rejected_credentials(status: int) -> None:
    """Authentication status codes are classified as invalid credentials."""
    session = _session_with_response(status=status)
    with pytest.raises(MonocleInvalidAuthError):
        await async_login("user", "bad", session=session)


async def test_login_http_failure() -> None:
    """Unexpected HTTP failures are classified as connection errors."""
    session = _session_with_response(status=503, text="maintenance")
    with pytest.raises(MonocleConnectionError, match="HTTP 503"):
        await async_login("user", "secret", session=session)


async def test_login_invalid_json() -> None:
    """A malformed successful response is rejected."""
    session = _session_with_response(json_error=ValueError("bad json"))
    with pytest.raises(MonocleConnectionError, match="invalid JSON"):
        await async_login("user", "secret", session=session)


async def test_login_transport_failure() -> None:
    """aiohttp transport failures are normalized."""
    session = MagicMock()
    session.post.side_effect = aiohttp.ClientError("offline")
    with pytest.raises(MonocleConnectionError, match="Unable to connect"):
        await async_login("user", "secret", session=session)


@pytest.mark.parametrize(
    "payload",
    [
        {"locationId": "42"},
        {"accessToken": "token"},
    ],
)
async def test_login_requires_token_and_location(payload: dict[str, str]) -> None:
    """Required response fields must be present."""
    session = _session_with_response(json_data=payload)
    with pytest.raises(MonocleConnectionError, match="missing required fields"):
        await async_login("user", "secret", session=session)


async def test_optional_numeric_metadata_is_best_effort() -> None:
    """Bad optional numeric metadata does not invalidate authentication."""
    session = _session_with_response(
        json_data={
            "accessToken": "token",
            "locationId": "42",
            "tokenExpiryMS": "not-an-int",
        }
    )
    result = await async_login("user", "secret", session=session)
    assert result.token_expiry_ms is None


AUTH = MonocleAuthSession(
    access_token="old-token",
    location_id="42",
    token_expiry_ms=None,
    user_id=None,
    email=None,
    display_name=None,
)


async def test_auth_manager_refresh_after_rejection() -> None:
    """A rejected token is replaced with a newly logged-in token."""
    refreshed = MonocleAuthSession(
        access_token="new-token",
        location_id="42",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )
    manager = MonocleAuthManager(
        "user@example.com",
        "secret",
        session=MagicMock(),
        auth=AUTH,
    )

    with patch(
        "custom_components.ha_monocle_cloud_status.auth.async_login",
        new=AsyncMock(return_value=refreshed),
    ) as login:
        result = await manager.async_refresh_after_rejection("old-token")

    assert result.access_token == "new-token"
    assert manager.socket_auth()["token"] == "new-token"
    login.assert_awaited_once()


async def test_auth_manager_concurrent_rejection_reuses_refreshed_token() -> None:
    """A stale rejected token does not cause a second login."""
    refreshed = MonocleAuthSession(
        access_token="new-token",
        location_id="42",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )
    manager = MonocleAuthManager(
        "user@example.com",
        "secret",
        session=MagicMock(),
        auth=AUTH,
    )

    with patch(
        "custom_components.ha_monocle_cloud_status.auth.async_login",
        new=AsyncMock(return_value=refreshed),
    ) as login:
        await manager.async_refresh_after_rejection("old-token")
        result = await manager.async_refresh_after_rejection("old-token")

    assert result.access_token == "new-token"
    login.assert_awaited_once()


async def test_auth_manager_invalid_refresh_requests_reauth_once() -> None:
    """Invalid stored credentials request HA reauthentication once."""
    reauth = MagicMock()
    manager = MonocleAuthManager(
        "user@example.com",
        "secret",
        session=MagicMock(),
        auth=AUTH,
        reauth_callback=reauth,
    )

    with (
        patch(
            "custom_components.ha_monocle_cloud_status.auth.async_login",
            new=AsyncMock(side_effect=MonocleInvalidAuthError()),
        ),
        pytest.raises(MonocleInvalidAuthError),
    ):
        await manager.async_refresh_after_rejection("old-token")

    manager.request_reauth()
    reauth.assert_called_once_with()


async def test_auth_manager_rejects_location_change() -> None:
    """Refresh cannot silently move an entry to a different location."""
    manager = MonocleAuthManager(
        "user@example.com",
        "secret",
        session=MagicMock(),
        auth=AUTH,
        reauth_callback=MagicMock(),
    )
    refreshed = MonocleAuthSession(
        access_token="new-token",
        location_id="99",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )

    with (
        patch(
            "custom_components.ha_monocle_cloud_status.auth.async_login",
            new=AsyncMock(return_value=refreshed),
        ),
        pytest.raises(MonocleInvalidAuthError, match="different location"),
    ):
        await manager.async_refresh_after_rejection("old-token")


async def test_auth_manager_refreshes_plausible_expiring_epoch_token() -> None:
    """An absolute tokenExpiryMS close to expiry triggers proactive refresh."""
    now_ms = 1_800_000_000_000
    expiring = MonocleAuthSession(
        access_token="old-token",
        location_id="42",
        token_expiry_ms=now_ms + 60_000,
        user_id=None,
        email=None,
        display_name=None,
    )
    refreshed = MonocleAuthSession(
        access_token="new-token",
        location_id="42",
        token_expiry_ms=now_ms + 3_600_000,
        user_id=None,
        email=None,
        display_name=None,
    )
    manager = MonocleAuthManager(
        "user@example.com",
        "secret",
        session=MagicMock(),
        auth=expiring,
    )

    with (
        patch(
            "custom_components.ha_monocle_cloud_status.auth.time.time",
            return_value=now_ms / 1000,
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.auth.async_login",
            new=AsyncMock(return_value=refreshed),
        ) as login,
    ):
        result = await manager.async_refresh_if_needed()

    assert result.access_token == "new-token"
    login.assert_awaited_once()


async def test_auth_manager_ignores_non_epoch_expiry_values() -> None:
    """Unknown tokenExpiryMS semantics do not cause a login loop."""
    manager = MonocleAuthManager(
        "user@example.com",
        "secret",
        session=MagicMock(),
        auth=MonocleAuthSession(
            access_token="token",
            location_id="42",
            token_expiry_ms=12345,
            user_id=None,
            email=None,
            display_name=None,
        ),
    )

    with patch(
        "custom_components.ha_monocle_cloud_status.auth.async_login",
        new=AsyncMock(),
    ) as login:
        result = await manager.async_refresh_if_needed()

    assert result.access_token == "token"
    login.assert_not_awaited()
