"""Authentication helpers for Monocle Cloud Status."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import Any

import aiohttp

from .const import LOGIN_URL, ORIGIN

_LOGGER = logging.getLogger(__name__)

_TOKEN_REFRESH_MARGIN_MS = 5 * 60 * 1000
_TOKEN_REFRESH_RETRY_SECONDS = 60
_TOKEN_REFRESH_IDLE_SECONDS = 60 * 60
_MIN_PLAUSIBLE_EPOCH_MS = 946684800000  # 2000-01-01T00:00:00Z
_MAX_PLAUSIBLE_EPOCH_MS = 4102444800000  # 2100-01-01T00:00:00Z

ReauthCallback = Callable[[], None]


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


class MonocleAuthManager:
    """Own and refresh runtime Monocle authentication."""

    def __init__(
        self,
        username: str,
        password: str,
        *,
        session: aiohttp.ClientSession,
        auth: MonocleAuthSession,
        reauth_callback: ReauthCallback | None = None,
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._auth = auth
        self._reauth_callback = reauth_callback
        self._refresh_lock = asyncio.Lock()
        self._reauth_requested = False

    @property
    def auth(self) -> MonocleAuthSession:
        """Return the current authentication session."""
        return self._auth

    @property
    def location_id(self) -> str:
        """Return the configured Monocle location identifier."""
        return self._auth.location_id

    def socket_auth(self) -> dict[str, str]:
        """Return current Socket.IO authentication data.

        python-socketio calls this function again for reconnection attempts,
        allowing a refreshed token to be used without rebuilding the client.
        """
        return {
            "token": self._auth.access_token,
            "locationId": self._auth.location_id,
        }

    async def async_refresh_if_needed(self) -> MonocleAuthSession:
        """Refresh the access token when a plausible expiry is approaching."""
        if not self._token_needs_refresh():
            return self._auth
        return await self._async_refresh(
            expected_access_token=self._auth.access_token,
            force=False,
            request_reauth_on_invalid=True,
        )

    async def async_refresh_after_rejection(
        self, rejected_access_token: str
    ) -> MonocleAuthSession:
        """Refresh after an API request rejects the current access token."""
        return await self._async_refresh(
            expected_access_token=rejected_access_token,
            force=True,
            request_reauth_on_invalid=True,
        )

    async def async_refresh_loop(self) -> None:
        """Keep a time-based access token refreshed for long-running sockets."""
        while True:
            delay = self._seconds_until_refresh()
            await asyncio.sleep(_TOKEN_REFRESH_IDLE_SECONDS if delay is None else delay)

            if not self._token_needs_refresh():
                continue

            try:
                await self.async_refresh_if_needed()
            except MonocleInvalidAuthError:
                # Reauth has already been requested by the refresh path.
                return
            except MonocleConnectionError:
                _LOGGER.debug(
                    "Unable to refresh Monocle authentication; retrying later",
                    exc_info=True,
                )
                await asyncio.sleep(_TOKEN_REFRESH_RETRY_SECONDS)

    def request_reauth(self) -> None:
        """Request Home Assistant reauthentication once."""
        if self._reauth_requested:
            return
        self._reauth_requested = True
        if self._reauth_callback is not None:
            self._reauth_callback()

    async def _async_refresh(
        self,
        *,
        expected_access_token: str,
        force: bool,
        request_reauth_on_invalid: bool,
    ) -> MonocleAuthSession:
        """Refresh the token, coalescing concurrent refresh attempts."""
        async with self._refresh_lock:
            # Another coroutine may already have replaced the rejected token.
            if self._auth.access_token != expected_access_token:
                return self._auth

            if not force and not self._token_needs_refresh():
                return self._auth

            try:
                refreshed = await async_login(
                    self._username,
                    self._password,
                    session=self._session,
                )
            except MonocleInvalidAuthError:
                if request_reauth_on_invalid:
                    self.request_reauth()
                raise

            if refreshed.location_id != self._auth.location_id:
                if request_reauth_on_invalid:
                    self.request_reauth()
                raise MonocleInvalidAuthError(
                    "Refreshed Monocle credentials returned a different location"
                )

            self._auth = refreshed
            return refreshed

    def _token_needs_refresh(self) -> bool:
        """Return whether tokenExpiryMS is a plausible near-expiry epoch value."""
        expiry_ms = self._absolute_expiry_ms()
        if expiry_ms is None:
            return False
        now_ms = int(time.time() * 1000)
        return expiry_ms <= now_ms + _TOKEN_REFRESH_MARGIN_MS

    def _seconds_until_refresh(self) -> float | None:
        """Return seconds until proactive refresh, or None for unknown expiry."""
        expiry_ms = self._absolute_expiry_ms()
        if expiry_ms is None:
            return None
        now_ms = int(time.time() * 1000)
        return max(0.0, (expiry_ms - _TOKEN_REFRESH_MARGIN_MS - now_ms) / 1000)

    def _absolute_expiry_ms(self) -> int | None:
        """Return token expiry only when it looks like an absolute Unix-ms value."""
        expiry_ms = self._auth.token_expiry_ms
        if expiry_ms is None:
            return None
        if not _MIN_PLAUSIBLE_EPOCH_MS <= expiry_ms <= _MAX_PLAUSIBLE_EPOCH_MS:
            return None
        return expiry_ms


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
