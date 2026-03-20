"""Config flow for Monocle Cloud Status."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .auth import MonocleAuthError, async_login
from .const import CONF_PASSWORD, CONF_USERNAME, DEFAULT_NAME, DOMAIN


class MonocleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monocle Cloud Status."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                auth = await async_login(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except MonocleAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
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
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )