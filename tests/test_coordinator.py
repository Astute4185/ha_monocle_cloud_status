"""Unit tests for the push coordinator."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ha_monocle_cloud_status.auth import MonocleAuthManager
from custom_components.ha_monocle_cloud_status.coordinator import MonocleCoordinator


async def test_coordinator_start_event_and_stop(hass) -> None:
    """Coordinator owns socket and authentication-refresh lifecycle."""
    entry = MagicMock()
    entry.pref_disable_polling = False
    entry.async_on_unload = MagicMock()

    refresh_tasks: list[asyncio.Task[None]] = []

    def _create_background_task(_hass, coroutine, name):
        task = asyncio.create_task(coroutine, name=name)
        refresh_tasks.append(task)
        return task

    entry.async_create_background_task = MagicMock(side_effect=_create_background_task)

    async def _refresh_loop() -> None:
        await asyncio.Event().wait()

    auth_manager = MagicMock(spec=MonocleAuthManager)
    auth_manager.location_id = "42"
    auth_manager.async_refresh_loop = MagicMock(side_effect=_refresh_loop)

    client = MagicMock()
    client.async_connect = AsyncMock()
    client.async_disconnect = AsyncMock()
    client.state = SimpleNamespace(latest_event={"mainsPWR": 10})

    with patch(
        "custom_components.ha_monocle_cloud_status.coordinator.MonocleSocketClient",
        return_value=client,
    ):
        coordinator = MonocleCoordinator(
            hass,
            entry,
            auth_manager,
            MagicMock(),
        )

    assert coordinator.location_id == "42"
    assert coordinator.selected_override_mode == "None"
    assert coordinator.selected_override_minutes == 60

    coordinator.async_set_updated_data = MagicMock()
    await coordinator.async_start()
    client.async_connect.assert_awaited_once()
    entry.async_create_background_task.assert_called_once()
    coordinator.async_set_updated_data.assert_called_with({"mainsPWR": 10})

    client.state.latest_event = {"solarPWR": 20}
    coordinator._async_on_event({})
    coordinator.async_set_updated_data.assert_called_with({"solarPWR": 20})

    await coordinator.async_stop()

    assert len(refresh_tasks) == 1
    assert refresh_tasks[0].cancelled()
    client.async_disconnect.assert_awaited_once()
