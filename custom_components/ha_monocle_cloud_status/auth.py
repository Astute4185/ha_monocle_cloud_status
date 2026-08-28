"""Authentication helpers for Monocle Cloud Status."""

from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import LOGIN_URL, ORIGIN


class MonocleAuthError(Exception):
    """Base exception for Monocle authentication failures."""


class MonocleInvalidAuthError(MonocleAuthError):
    """Raised when Monocle rejects supplied credentials."""


class MonocleConnectionError(MonocleAuthError):
    """Raised when the Monocle authentication service cannot be reached."""


@dataclass(slots=True)
class MonocleAuthSession:
    """Authentication result returned by the Monocle login endpoint."""

    access_token: str
    location_id: str
    token_expiry_ms: int | None
    user_id: str | None
    email: str | None
    display_name: str | None


async def async_login(
    username: str,
    password: str,
    *,
    session: aiohttp.ClientSession,
    timeout_seconds: int = 20,
) -> MonocleAuthSession:
    """Authenticate against Monocle and return session metadata."""
    payload = {"username": username, "password": password}
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": ORIGIN,
        "Referer": f"{ORIGIN}/",
    }

    try:
        async with session.post(
            LOGIN_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
        ) as response:
            raw_text = await response.text()
            if response.status in {401, 403}:
                raise MonocleInvalidAuthError("Invalid Monocle username or password")
            if not 200 <= response.status < 300:
                raise MonocleConnectionError(
                    f"Login failed with HTTP {response.status}: {raw_text[:200]}"
                )
            try:
                data: dict[str, Any] = await response.json()
            except (aiohttp.ContentTypeError, ValueError) as err:
                raise MonocleConnectionError(
                    "Login returned an invalid JSON response"
                ) from err
    except MonocleAuthError:
        raise
    except (aiohttp.ClientError, TimeoutError) as err:
        raise MonocleConnectionError("Unable to connect to Monocle") from err

    access_token = data.get("accessToken")
    location_id = data.get("locationId")
    if not access_token or location_id is None:
        raise MonocleConnectionError("Login response is missing required fields")

    return MonocleAuthSession(
        access_token=str(access_token),
        location_id=str(location_id),
        token_expiry_ms=_safe_int(data.get("tokenExpiryMS")),
        user_id=_safe_str(data.get("id")),
        email=_safe_str(data.get("email")),
        display_name=_safe_str(data.get("displayName")),
    )


def _safe_str(value: Any) -> str | None:
    """Convert a value to a string while preserving None."""
    return None if value is None else str(value)


def _safe_int(value: Any) -> int | None:
    """Convert a value to an integer if possible."""
    if value is None:
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None
