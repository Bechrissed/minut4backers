"""Constants for the Minut Point integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "minut4backers"

# Supported platforms. Sensors and binary sensors are implemented.
PLATFORMS: Final = ["sensor", "binary_sensor"]

# Default scan interval for polling the API. Minut sensors update roughly every
# hour in the official integration, but the API used here allows more frequent
# polling. A 60 second interval offers near‑real‑time values without risking
# hitting the documented rate limits【309709768529123†L230-L263】.
SCAN_INTERVAL: Final = timedelta(seconds=15)

# Configuration keys used in the config flow and stored in the config entry
CONF_USER_ID: Final = "user_id"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"

SENSOR_TYPES: Final = {
    "temperature": {
        "name": "Temperature",
        "unit": "°C",
        "device_class": "temperature",
        "state_class": "measurement",
    },
    "humidity": {
        "name": "Humidity",
        "unit": "%",
        "device_class": "humidity",
        "state_class": "measurement",
    },
    "noise": {
        "name": "Noise Level",
        "unit": "dBA",
        "device_class": None,
        "state_class": "measurement",
    },
}

# Binary sensor mapping for timeline events. Each key corresponds to the binary
# sensor name in Home Assistant and maps to a list of event types that should
# trigger the sensor. When an event occurs, the binary sensor will be set to on
# for a short period before clearing.
BINARY_SENSOR_EVENTS: Final = {
    "motion": {
        "event_types": ["activity_detected"],
        "device_class": "motion",
    },
    "alarm": {
        "event_types": ["alarm_heard", "avg_sound_high", "sound_level_dropped_normal"],
        "device_class": "sound",
    },
}