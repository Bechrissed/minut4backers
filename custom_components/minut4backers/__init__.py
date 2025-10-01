"""Minut Point HACS integration.

This custom integration allows you to integrate Minut Point sensors into Home
Assistant using the same tokens used by the Minut web dashboard. It polls the
Minut REST API for sensor readings and recent events and exposes them as
entities in Home Assistant. Both regular sensor values (temperature, humidity
and noise level) and binary sensors (motion and alarm) are supported.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import MinutAPI
from .const import DOMAIN, PLATFORMS, SCAN_INTERVAL
from .coordinator import MinutDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Minut component from yaml (unsupported)."""
    # This integration is set up via config flow only
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Minut from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = hass.helpers.aiohttp_client.async_get_clientsession()

    # Read stored credentials
    user_id: str = entry.data.get("user_id")
    access_token: str = entry.data.get("access_token")
    refresh_token: str | None = entry.data.get("refresh_token")

    api = MinutAPI(session, user_id=user_id, access_token=access_token, refresh_token=refresh_token)

    coordinator = MinutDataUpdateCoordinator(hass, api, SCAN_INTERVAL)

    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        raise ConfigEntryNotReady("Error communicating with Minut API") from err

    # Store coordinator for platforms to access
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok