from __future__ import annotations

from typing import Any, Dict
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .api import MinutAPI, MinutAuthError, MinutRateLimitError, MinutConnectError, Tokens
from aiohttp import ClientSession

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

        session: ClientSession = self.hass.helpers.aiohttp_client.async_get_clientsession()

        api = MinutAPI(session)
        try:
            tokens: Tokens
            if has_creds:
                tokens = await api.password_login(user_input["username"], user_input["password"])
                # persist original creds as well (some users like both)
                user_input["user_id"] = tokens.user_id
                user_input["access_token"] = tokens.access_token
                user_input["refresh_token"] = tokens.refresh_token
            else:
                tokens = Tokens(
                    access_token=user_input["access_token"],
                    refresh_token=user_input.get("refresh_token"),
                    user_id=user_input.get("user_id"),
                )

            # Validate by listing devices (401/403 will surface properly)
            await api.get_devices(tokens)

        except MinutAuthError:
            errors["base"] = "invalid_auth"
        except MinutRateLimitError:
            errors["base"] = "rate_limited"
        except MinutConnectError:
            errors["base"] = "cannot_connect"
        except Exception:
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

        return self.async_create_entry(title="Minut Account", data=user_input)
    
    #test