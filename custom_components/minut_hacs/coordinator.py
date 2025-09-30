"""DataUpdateCoordinator for the Minut HACS integration.

This coordinator centralises the polling logic for Minut devices. It retrieves
the list of devices, fetches sensor values for each device and examines
recent timeline events to derive binary sensor states. The coordinator is
responsible for periodically refreshing data and making it available to the
entity platforms.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MinutAPI
from .const import SENSOR_TYPES, BINARY_SENSOR_EVENTS


_LOGGER = logging.getLogger(__name__)


class MinutDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to manage data fetching for Minut."""

    def __init__(self, hass: HomeAssistant, api: MinutAPI, scan_interval: timedelta) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Minut HACS data coordinator",
            update_interval=scan_interval,
        )
        self.api = api
        self._devices: list[Mapping[str, Any]] | None = None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Minut.

        This method is called by the DataUpdateCoordinator at each polling
        interval. It gathers the latest sensor values and recent events for
        each device. If any call fails, an UpdateFailed exception is raised
        which will be logged by Home Assistant.
        """
        try:
            # Fetch the device list once. Devices rarely change and this reduces API calls.
            if self._devices is None:
                self._devices = await self.api.get_devices()
                _LOGGER.debug("Loaded %s devices from Minut", len(self._devices))

            devices_data: Dict[str, Any] = {}
            # Fetch latest events across all devices once per update
            events_by_device = await self.api.get_recent_events()

            # Iterate through each device and fetch sensor values
            for device in self._devices:
                device_id = str(device.get("id") or device.get("device_id"))
                if not device_id:
                    continue
                sensors: Dict[str, Any] = {}
                for key in SENSOR_TYPES:
                    value = await self.api.get_latest_sensor_value(device_id, key)
                    sensors[key] = value
                # Derive binary sensor states from events
                device_events = events_by_device.get(device_id, [])
                binary_states: Dict[str, bool] = {}
                for binary_key, config in BINARY_SENSOR_EVENTS.items():
                    # Set state to True if any matching event occurred recently
                    state = any(evt in device_events for evt in config["event_types"])
                    binary_states[binary_key] = state
                devices_data[device_id] = {
                    "device": device,
                    "sensors": sensors,
                    "binary": binary_states,
                }
            return devices_data
        except Exception as err:
            raise UpdateFailed(f"Error fetching data from Minut API: {err}") from err