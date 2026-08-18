#!/usr/bin/env python3
"""Home Assistant runtime compatibility smoke test.

This test never contacts Monocle. It imports every integration module, checks the stable
Intelli extension contract, constructs a real Home Assistant object, and exercises the
Monocle coordinator lifecycle with the network client replaced by a local stub.
"""

import asyncio
from dataclasses import fields
from importlib import import_module, metadata
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MODULE_NAMES = (
    "__init__",
    "auth",
    "binary_sensor",
    "button",
    "client",
    "config_flow",
    "const",
    "coordinator",
    "entity",
    "extension",
    "number",
    "select",
    "sensor",
)


class _SmokeConfigEntry:
    """Minimum config-entry surface used by DataUpdateCoordinator."""

    pref_disable_polling = False

    def __init__(self) -> None:
        self.unload_callbacks = []

    def async_on_unload(self, callback) -> None:
        """Capture coordinator shutdown registration."""
        self.unload_callbacks.append(callback)


class _SmokeClient:
    """Network-free client used to exercise the coordinator lifecycle."""

    def __init__(self, state) -> None:
        self.state = state

    async def async_connect(self) -> None:
        """Simulate a socket connection and one pushed event."""
        self.state.connected = True
        self.state.latest_event = {"smoke": True}

    async def async_disconnect(self) -> None:
        """Simulate socket shutdown."""
        self.state.connected = False


async def _async_runtime_smoke(prefix: str) -> None:
    """Construct Home Assistant and run the push coordinator without network I/O."""
    from homeassistant.core import HomeAssistant

    auth_module = import_module(f"{prefix}.auth")
    client_module = import_module(f"{prefix}.client")
    coordinator_module = import_module(f"{prefix}.coordinator")

    auth = auth_module.MonocleAuthSession(
        access_token="smoke-token",
        location_id="1",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )
    state = client_module.MonocleState()
    smoke_client = _SmokeClient(state)
    entry = _SmokeConfigEntry()

    with TemporaryDirectory() as config_dir:
        hass = HomeAssistant(config_dir)
        try:
            with patch.object(
                coordinator_module,
                "MonocleSocketClient",
                return_value=smoke_client,
            ):
                coordinator = coordinator_module.MonocleCoordinator(
                    hass,
                    entry,
                    auth,
                    object(),
                )

            if not entry.unload_callbacks:
                raise AssertionError(
                    "Coordinator did not register config-entry shutdown"
                )

            await coordinator.async_start()
            if (
                coordinator.data != {"smoke": True}
                or not coordinator.client.state.connected
            ):
                raise AssertionError("Coordinator did not publish the smoke event")

            await coordinator.async_stop()
            await coordinator.async_shutdown()
            if coordinator.client.state.connected:
                raise AssertionError("Coordinator client remained connected after stop")
        finally:
            hass.import_executor.shutdown(wait=True)


def _validate_extension_contract(prefix: str) -> None:
    """Validate the public surface consumed by the private Intelli integration."""
    extension = import_module(f"{prefix}.extension")
    state_type = extension.MonocleExtensionState
    contract_fields = {field.name for field in fields(state_type)}
    expected_fields = {"connected", "actor_id", "location_id"}
    if contract_fields != expected_fields:
        raise AssertionError(
            f"Intelli compatibility contract changed: {contract_fields!r}"
        )

    for name in ("get_parent_coordinator", "get_extension_state"):
        if not callable(getattr(extension, name, None)):
            raise AssertionError(f"Missing Intelli compatibility function: {name}")


def main() -> int:
    """Import integration modules and run network-free HA runtime checks."""
    prefix = "custom_components.ha_monocle_cloud_status"
    for module_name in MODULE_NAMES:
        module = prefix if module_name == "__init__" else f"{prefix}.{module_name}"
        import_module(module)

    _validate_extension_contract(prefix)
    asyncio.run(_async_runtime_smoke(prefix))

    print(f"Home Assistant: {metadata.version('homeassistant')}")
    print("Monocle Home Assistant runtime/API smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
