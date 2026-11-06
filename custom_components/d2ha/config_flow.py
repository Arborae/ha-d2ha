"""Config flow for the D2HA integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import D2HAAuthError, D2HAClient, D2HAConnectionError, D2HAError
from .const import CONF_TOKEN, CONF_URL, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_TOKEN): str,
    }
)


def normalize_url(url: str) -> str:
    """One spelling for one server: no trailing slash, scheme required."""
    url = url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


class D2HAConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup and re-authentication of a D2HA entry."""

    VERSION = 1

    async def _validate(self, url: str, token: str) -> dict[str, Any]:
        """Ask D2HA for /info; raise on failure, return the payload."""
        client = D2HAClient(async_get_clientsession(self.hass), url, token)
        return await client.info()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            token = user_input[CONF_TOKEN].strip()
            try:
                await self._validate(url, token)
            except D2HAAuthError:
                errors["base"] = "invalid_auth"
            except D2HAConnectionError:
                errors["base"] = "cannot_connect"
            except D2HAError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="D2HA",
                    data={CONF_URL: url, CONF_TOKEN: token},
                )
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """The token was revoked or changed: ask for a new one."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            try:
                await self._validate(entry.data[CONF_URL], token)
            except D2HAAuthError:
                errors["base"] = "invalid_auth"
            except D2HAConnectionError:
                errors["base"] = "cannot_connect"
            except D2HAError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data={**entry.data, CONF_TOKEN: token}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )
