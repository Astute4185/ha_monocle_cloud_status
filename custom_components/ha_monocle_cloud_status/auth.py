"""Authentication helpers for Monocle Cloud Status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import LOGIN_URL, ORIGIN


class MonocleAuthError(Exception):
    """Raised when Monocle authentication fails."""


@dataclass(slots=True)
class MonocleAuthSession:
    """Authentication result returned by /auth/login."""

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
    session: aiohttp.ClientSession | None = None,
    timeout_seconds: int = 20,
) -> MonocleAuthSession:
    """Authenticate against Monocle and return auth/session metadata."""
    owns_session = session is None
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    if owns_session:
        session = aiohttp.ClientSession(timeout=timeout)

    assert session is not None

    try:
        payload = {
            "username": username,
            "password": password,
        }

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": ORIGIN,
            "Referer": f"{ORIGIN}/",
        }

        async with session.post(LOGIN_URL, json=payload, headers=headers) as resp:
            raw_text = await resp.text()

            if not 200 <= resp.status < 300:
                raise MonocleAuthError(
                    f"Login failed with HTTP {resp.status}: {raw_text[:500]}"
                )

            try:
                data: dict[str, Any] = await resp.json()
            except Exception as err:
                raise MonocleAuthError(
                    f"Login returned non-JSON response: {raw_text[:500]}"
                ) from err

        access_token = data.get("accessToken")
        location_id = data.get("locationId")

        if not access_token:
            raise MonocleAuthError("Login response did not include accessToken")

        if location_id is None:
            raise MonocleAuthError("Login response did not include locationId")

        return MonocleAuthSession(
            access_token=str(access_token),
            location_id=str(location_id),
            token_expiry_ms=_safe_int(data.get("tokenExpiryMS")),
            user_id=_safe_str(data.get("id")),
            email=_safe_str(data.get("email")),
            display_name=_safe_str(data.get("displayName")),
        )
    except aiohttp.ClientError as err:
        raise MonocleAuthError(f"Network error during login: {err}") from err
    finally:
        if owns_session:
            await session.close()


def _safe_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None