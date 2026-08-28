"""Unit tests for Monocle telemetry parsing."""

from datetime import UTC, datetime

from custom_components.ha_monocle_cloud_status.auth import MonocleAuthSession
from custom_components.ha_monocle_cloud_status.client import (
    MonocleSocketClient,
    MonocleState,
)


def _parser_client() -> MonocleSocketClient:
    client = object.__new__(MonocleSocketClient)
    client._auth = MonocleAuthSession(
        access_token="token",
        location_id="42",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )
    client.state = MonocleState()
    return client


def test_parse_complete_event() -> None:
    """A representative push event populates the public state model."""
    client = _parser_client()
    client._handle_event(
        {
            "mainsPWR": "101.5",
            "solarPWR": 2500,
            "housePWR": "900",
            "batteryPWR": None,
            "phyDev": [{"online": True}],
            "channels": [{"id": "channel-1"}],
            "controllable": {
                "OTHER": [
                    {
                        "id": "actor-1",
                        "state": "ON",
                        "override": {
                            "fields": [
                                {"id": "mode", "currentValue": "OFF"},
                                {"id": "validUntil", "currentValue": "1700000000000"},
                            ]
                        },
                    }
                ]
            },
        }
    )

    assert client.state.mains_pwr == 101.5
    assert client.state.solar_pwr == 2500.0
    assert client.state.house_pwr == 900.0
    assert client.state.battery_pwr is None
    assert client.state.device_online is True
    assert client.state.load_state == "on"
    assert client.state.actor_id == "actor-1"
    assert client.state.location_id == 42
    assert client.state.override_mode == "off"
    assert client.state.override_valid_until == datetime.fromtimestamp(
        1_700_000_000, tz=UTC
    )


def test_parse_malformed_event_is_safe() -> None:
    """Unexpected payload shapes do not crash telemetry parsing."""
    client = _parser_client()
    client._handle_event(
        {
            "mainsPWR": "not-a-number",
            "phyDev": "invalid",
            "channels": {},
            "controllable": [],
        }
    )

    assert client.state.mains_pwr is None
    assert client.state.raw_phydev == []
    assert client.state.raw_channels == []
    assert client.state.actor_id is None
    assert client.state.override_mode is None
