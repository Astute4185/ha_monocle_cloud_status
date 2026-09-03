"""Tests for integration setup and unload behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ha_monocle_cloud_status import (
    async_setup_entry,
    async_unload_entry,
)
from custom_components.ha_monocle_cloud_status.auth import (
    MonocleAuthManager,
    MonocleAuthSession,
    MonocleConnectionError,
    MonocleInvalidAuthError,
)
from custom_components.ha_monocle_cloud_status.client import MonocleClientError
from custom_components.ha_monocle_cloud_status.const import CONF_PASSWORD, CONF_USERNAME
import pytest

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

AUTH = MonocleAuthSession(
    access_token="token",
    location_id="123",
    token_expiry_ms=None,
    user_id=None,
    email=None,
    display_name=None,
)


def _entry():
    return SimpleNamespace(
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
        runtime_data=None,
    )


async def test_setup_success() -> None:
    """Successful setup stores typed runtime data and forwards platforms."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    entry = _entry()
    coordinator = MagicMock()
    coordinator.async_start = AsyncMock()
    coordinator.async_stop = AsyncMock()

    auth_manager = MagicMock(spec=MonocleAuthManager)

    with (
        patch(
            "custom_components.ha_monocle_cloud_status.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.async_login",
            new=AsyncMock(return_value=AUTH),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.MonocleAuthManager",
            return_value=auth_manager,
        ) as manager_cls,
        patch(
            "custom_components.ha_monocle_cloud_status.MonocleCoordinator",
            return_value=coordinator,
        ) as coordinator_cls,
    ):
        assert await async_setup_entry(hass, entry) is True

    assert entry.runtime_data.coordinator is coordinator
    manager_cls.assert_called_once()
    coordinator_cls.assert_called_once()
    assert coordinator_cls.call_args.args[2] is auth_manager
    coordinator.async_start.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (MonocleInvalidAuthError(), ConfigEntryAuthFailed),
        (MonocleConnectionError(), ConfigEntryNotReady),
    ],
)
async def test_setup_login_errors(error: Exception, expected: type[Exception]) -> None:
    """Authentication and transport failures use HA config-entry exceptions."""
    hass = MagicMock()
    entry = _entry()
    with (
        patch(
            "custom_components.ha_monocle_cloud_status.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.async_login",
            new=AsyncMock(side_effect=error),
        ),
        pytest.raises(expected),
    ):
        await async_setup_entry(hass, entry)


async def test_socket_failure_is_not_ready() -> None:
    """A socket startup failure requests HA retry setup later."""
    hass = MagicMock()
    entry = _entry()
    coordinator = MagicMock()
    coordinator.async_start = AsyncMock(side_effect=MonocleClientError())

    with (
        patch(
            "custom_components.ha_monocle_cloud_status.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.async_login",
            new=AsyncMock(return_value=AUTH),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.MonocleAuthManager",
            return_value=MagicMock(spec=MonocleAuthManager),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.MonocleCoordinator",
            return_value=coordinator,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, entry)


async def test_forward_failure_stops_client() -> None:
    """Partially started clients are stopped when platform setup fails."""
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(
        side_effect=RuntimeError("platform failed")
    )
    entry = _entry()
    coordinator = MagicMock()
    coordinator.async_start = AsyncMock()
    coordinator.async_stop = AsyncMock()

    with (
        patch(
            "custom_components.ha_monocle_cloud_status.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.async_login",
            new=AsyncMock(return_value=AUTH),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.MonocleAuthManager",
            return_value=MagicMock(spec=MonocleAuthManager),
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.MonocleCoordinator",
            return_value=coordinator,
        ),
        pytest.raises(RuntimeError, match="platform failed"),
    ):
        await async_setup_entry(hass, entry)

    coordinator.async_stop.assert_awaited_once()


async def test_unload_stops_client() -> None:
    """Unload tears down platforms before disconnecting the socket."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    coordinator = MagicMock()
    coordinator.async_stop = AsyncMock()
    entry = SimpleNamespace(runtime_data=SimpleNamespace(coordinator=coordinator))

    assert await async_unload_entry(hass, entry) is True
    coordinator.async_stop.assert_awaited_once()


async def test_unload_failure_keeps_client_running() -> None:
    """A failed platform unload does not disconnect runtime data prematurely."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    coordinator = MagicMock()
    coordinator.async_stop = AsyncMock()
    entry = SimpleNamespace(runtime_data=SimpleNamespace(coordinator=coordinator))

    assert await async_unload_entry(hass, entry) is False
    coordinator.async_stop.assert_not_awaited()
