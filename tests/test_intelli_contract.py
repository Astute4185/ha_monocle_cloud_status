"""Contract tests for the private ha_monocle_cloud_status_intelli companion.

The private integration is intentionally not required in CI. These tests lock the parent
surface the companion needs, so parent refactors fail before they silently break it.
"""

from dataclasses import fields
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.ha_monocle_cloud_status.client import MonocleState
from custom_components.ha_monocle_cloud_status.const import DOMAIN
from custom_components.ha_monocle_cloud_status.coordinator import MonocleCoordinator
from custom_components.ha_monocle_cloud_status.extension import (
    MonocleExtensionState,
    get_extension_state,
    get_parent_coordinator,
)

REQUIRED_STATE_FIELDS = {"connected", "actor_id", "location_id"}


def test_intelli_required_state_fields_exist() -> None:
    """The parent telemetry model keeps all values consumed by Intelli."""
    state_fields = {field.name for field in fields(MonocleState)}
    assert state_fields >= REQUIRED_STATE_FIELDS


def test_intelli_parent_coordinator_contract_is_stable() -> None:
    """The companion can still identify the parent location for device registry use."""
    assert "location_id" in MonocleCoordinator.__annotations__


def test_intelli_public_extension_contract_is_stable() -> None:
    """The public companion view exposes only the intentionally supported fields."""
    assert {
        field.name for field in fields(MonocleExtensionState)
    } == REQUIRED_STATE_FIELDS

    coordinator = SimpleNamespace(
        client=SimpleNamespace(
            state=SimpleNamespace(connected=True, actor_id="actor-1", location_id=42)
        )
    )
    assert get_extension_state(coordinator) == MonocleExtensionState(
        connected=True,
        actor_id="actor-1",
        location_id=42,
    )


def test_intelli_can_resolve_parent_from_runtime_data() -> None:
    """The companion resolves the parent via ConfigEntry.runtime_data, not hass.data."""
    coordinator = object()
    entry = SimpleNamespace(
        domain=DOMAIN,
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = entry

    assert get_parent_coordinator(hass, "entry-id") is coordinator
    hass.config_entries.async_get_entry.assert_called_once_with("entry-id")


def test_intelli_parent_resolution_rejects_wrong_entry() -> None:
    """Missing or unrelated config entries are not exposed to companions."""
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = SimpleNamespace(
        domain="other",
        runtime_data=None,
    )
    assert get_parent_coordinator(hass, "entry-id") is None


def test_intelli_parent_resolution_rejects_unloaded_entry() -> None:
    """A parent entry without runtime data is not ready for companion use."""
    hass = MagicMock()
    hass.config_entries.async_get_entry.return_value = SimpleNamespace(
        domain=DOMAIN,
        runtime_data=None,
    )
    assert get_parent_coordinator(hass, "entry-id") is None
