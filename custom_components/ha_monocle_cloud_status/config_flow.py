"""Config flow for Monocle Cloud Status."""

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .auth import (
    MonocleAuthSession,
    MonocleConnectionError,
    MonocleInvalidAuthError,
    async_login,
)
from .const import CONF_PASSWORD, CONF_USERNAME, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _credential_schema(*, username: str | None = None) -> vol.Schema:
    """Return the credential form schema."""
    username_key = (
        vol.Required(CONF_USERNAME, default=username)
        if username is not None
        else vol.Required(CONF_USERNAME)
    )
    return vol.Schema(
        {
            username_key: TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.EMAIL,
                    autocomplete="username",
                )
            ),
            vol.Required(CONF_PASSWORD): TextSelector(
                TextSelectorConfig(
                    type=TextSelectorType.PASSWORD,
                    autocomplete="current-password",
                )
            ),
        }
    )


class MonocleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monocle Cloud Status."""

    VERSION = 1

    async def _async_validate_credentials(
        self, user_input: Mapping[str, Any]
    ) -> tuple[MonocleAuthSession | None, dict[str, str]]:
        """Validate credentials and return an auth session or form errors."""
        try:
            auth = await async_login(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
        except MonocleInvalidAuthError:
            return None, {"base": "invalid_auth"}
        except MonocleConnectionError:
            return None, {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("Unexpected exception validating Monocle credentials")
            return None, {"base": "unknown"}
        return auth, {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            auth, errors = await self._async_validate_credentials(user_input)
            if auth is not None:
                await self.async_set_unique_id(str(auth.location_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} {auth.location_id}",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_credential_schema(),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication for an existing config entry."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement credentials and reload the config entry."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            auth, errors = await self._async_validate_credentials(user_input)
            if auth is not None:
                if (
                    reauth_entry.unique_id is not None
                    and str(auth.location_id) != reauth_entry.unique_id
                ):
                    errors["base"] = "wrong_account"
                else:
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_credential_schema(
                username=reauth_entry.data[CONF_USERNAME],
            ),
            errors=errors,
        )
