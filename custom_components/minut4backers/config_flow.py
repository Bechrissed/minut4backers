from __future__ import annotations

import logging
from typing import Any, Dict
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .api import (
    MinutAPI,
    MinutAuthError,
    MinutRateLimitError,
    MinutConnectError,
    Tokens,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("username"): str,
        vol.Optional("password"): str,
        vol.Optional("user_id"): str,
        vol.Optional("access_token"): str,
        vol.Optional("refresh_token"): str,
    }
)

class MinutHacsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Minut Point (HACS)."""
    VERSION = 1

    async def async_step_user(self, user_input: Dict[str, Any] | None = None) -> FlowResult:
        errors: Dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        has_tokens = all(user_input.get(k) for k in ("user_id", "access_token", "refresh_token"))
        has_creds = all(user_input.get(k) for k in ("username", "password"))

        if not (has_tokens or has_creds):
            errors["base"] = "missing_auth"
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        # ✅ correct way to get the session
        session = aiohttp_client.async_get_clientsession(self.hass)
        api = MinutAPI(session)

        try:
            if has_creds:
                tokens = await api.password_login(user_input["username"], user_input["password"])
                user_input["user_id"] = tokens.user_id
                user_input["access_token"] = tokens.access_token
                user_input["refresh_token"] = tokens.refresh_token
            else:
                tokens = Tokens(
                    access_token=user_input["access_token"],
                    refresh_token=user_input.get("refresh_token"),
                    user_id=user_input.get("user_id"),
                )

            # Validate tokens/creds: list devices
            await api.get_devices(tokens)

        except MinutAuthError:
            errors["base"] = "invalid_auth"
        except MinutRateLimitError:
            errors["base"] = "rate_limited"
        except MinutConnectError:
            errors["base"] = "cannot_connect"
        except Exception as exc:
            # This is what turns “unknown error” into a useful stack trace in the HA logs
            _LOGGER.exception("Unexpected error in Minut config flow: %s", exc)
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        return self.async_create_entry(title="Minut Account", data=user_input)