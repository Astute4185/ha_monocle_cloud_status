"""Unit tests for Monocle authentication."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
from custom_components.ha_monocle_cloud_status.auth import (
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
