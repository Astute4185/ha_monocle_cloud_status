"""Unit tests for the push coordinator."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ha_monocle_cloud_status.auth import MonocleAuthSession
from custom_components.ha_monocle_cloud_status.coordinator import MonocleCoordinator

AUTH = MonocleAuthSession(
    access_token="token",
    location_id="42",
    token_expiry_ms=None,
    user_id=None,
    email=None,
    display_name=None,
)


async def test_coordinator_start_event_and_stop(hass) -> None:
    """The coordinator owns socket lifecycle and pushes updates to listeners."""
    entry = MagicMock()
    entry.pref_disable_polling = False
    entry.async_on_unload = MagicMock()
    client = MagicMock()
    client.async_connect = AsyncMock()
    client.async_disconnect = AsyncMock()
    client.state = SimpleNamespace(latest_event={"mainsPWR": 10})

    with patch(
        "custom_components.ha_monocle_cloud_status.coordinator.MonocleSocketClient",
        return_value=client,
    ):
        coordinator = MonocleCoordinator(hass, entry, AUTH, MagicMock())

    assert coordinator.location_id == "42"
    assert coordinator.selected_override_mode == "None"
    assert coordinator.selected_override_minutes == 60

    coordinator.async_set_updated_data = MagicMock()
    await coordinator.async_start()
    client.async_connect.assert_awaited_once()
    coordinator.async_set_updated_data.assert_called_with({"mainsPWR": 10})

    client.state.latest_event = {"solarPWR": 20}
    coordinator._async_on_event({})
    coordinator.async_set_updated_data.assert_called_with({"solarPWR": 20})

    await coordinator.async_stop()
    client.async_disconnect.assert_awaited_once()
