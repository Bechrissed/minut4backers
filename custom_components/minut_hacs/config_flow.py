"""Config flow for the Minut HACS integration.

This config flow allows the user to enter either their Minut login credentials
or API tokens obtained from the Minut web dashboard. When credentials are
provided, the integration will exchange them for an access token, refresh
token and user ID using the same endpoint employed by the web dashboard
【309709768529123†L230-L263】. If tokens are supplied directly, they are used as‑is.

The flow validates the tokens by fetching the list of devices. If the tokens
are invalid or the API is unavailable, a meaningful error is shown to the
user. Duplicate configuration (same user ID) is prevented.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .api import MinutAPI
from .const import (
    DOMAIN,
    CONF_USER_ID,
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_USERNAME as CONF_U,
    CONF_PASSWORD as CONF_P,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Minut HACS."""

    VERSION = 1

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step of the config flow."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            # Determine authentication method
            username = user_input.get(CONF_U)
            password = user_input.get(CONF_P)
            access_token = user_input.get(CONF_ACCESS_TOKEN)
            refresh_token = user_input.get(CONF_REFRESH_TOKEN)
            user_id = user_input.get(CONF_USER_ID)

            session = aiohttp_client.async_get_clientsession(self.hass)

            try:
                if username and password and not access_token:
                    # Use username/password to obtain tokens
                    user_id, access_token, refresh_token = await MinutAPI.authenticate(session, username, password)
                    _LOGGER.debug("Obtained tokens via password grant for user %s", user_id)
                # Validate required fields
                if not user_id or not access_token:
                    raise ValueError("Missing user_id or access_token")
                # Check for duplicate user
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                # Validate tokens by fetching devices
                api = MinutAPI(session, user_id=user_id, access_token=access_token, refresh_token=refresh_token)
                devices = await api.get_devices()
                if not devices:
                    _LOGGER.warning("No devices returned for user %s", user_id)
                # Create entry
                return self.async_create_entry(
                    title=f"Minut {user_id}",
                    data={
                        "user_id": user_id,
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                    },
                )
            except ValueError:
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.error("Error during Minut configuration: %s", err)
                errors["base"] = "cannot_connect"

        # Build the form schema. All fields are optional except access_token and user_id if
        # username/password are not supplied.
        schema = vol.Schema(
            {
                vol.Optional(CONF_U): str,
                vol.Optional(CONF_P): str,
                vol.Optional(CONF_USER_ID): str,
                vol.Optional(CONF_ACCESS_TOKEN): str,
                vol.Optional(CONF_REFRESH_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)