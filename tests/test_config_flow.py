"""Tests for the Monocle config flow."""

from unittest.mock import patch

from custom_components.ha_monocle_cloud_status.auth import (
    MonocleAuthSession,
    MonocleConnectionError,
    MonocleInvalidAuthError,
)
from custom_components.ha_monocle_cloud_status.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"}
AUTH = MonocleAuthSession(
    access_token="token",
    location_id="12345",
    token_expiry_ms=None,
    user_id="user-id",
    email="user@example.com",
    display_name="User",
)


async def test_user_form(hass) -> None:
    """The user flow starts with the credential form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_success(hass) -> None:
    """Valid credentials create a unique config entry."""
    with (
        patch(
            "custom_components.ha_monocle_cloud_status.config_flow.async_login",
            return_value=AUTH,
        ),
        patch(
            "custom_components.ha_monocle_cloud_status.async_setup_entry",
            return_value=True,
        ) as mock_setup,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Monocle 12345"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == "12345"
    assert len(mock_setup.mock_calls) == 1


async def test_invalid_auth(hass) -> None:
    """Rejected credentials report invalid_auth."""
    with patch(
        "custom_components.ha_monocle_cloud_status.config_flow.async_login",
        side_effect=MonocleInvalidAuthError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass) -> None:
    """Transport failures report cannot_connect."""
    with patch(
        "custom_components.ha_monocle_cloud_status.config_flow.async_login",
        side_effect=MonocleConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_unknown_error(hass) -> None:
    """Unexpected failures are surfaced as unknown without leaking details."""
    with patch(
        "custom_components.ha_monocle_cloud_status.config_flow.async_login",
        side_effect=RuntimeError("boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_duplicate_location_aborts(hass) -> None:
    """A Monocle location can only be configured once."""
    existing = MockConfigEntry(domain=DOMAIN, unique_id="12345", data=USER_INPUT)
    existing.add_to_hass(hass)

    with patch(
        "custom_components.ha_monocle_cloud_status.config_flow.async_login",
        return_value=AUTH,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass) -> None:
    """Replacement credentials update and reload the existing entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data=USER_INPUT,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing.entry_id,
        },
        data=existing.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    replacement = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "new-secret",
    }
    with patch(
        "custom_components.ha_monocle_cloud_status.config_flow.async_login",
        return_value=AUTH,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], replacement
        )

    assert result["type"] is FlowResultType.ABORT
    assert existing.data == replacement


async def test_reauth_rejects_different_location(hass) -> None:
    """Reauthentication cannot silently switch the configured Monocle location."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data=USER_INPUT,
    )
    existing.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": existing.entry_id,
        },
        data=existing.data,
    )
    other_auth = MonocleAuthSession(
        access_token="token",
        location_id="99999",
        token_expiry_ms=None,
        user_id=None,
        email=None,
        display_name=None,
    )
    with patch(
        "custom_components.ha_monocle_cloud_status.config_flow.async_login",
        return_value=other_auth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_account"}
