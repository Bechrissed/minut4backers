"""API client for the Minut REST API.

This module contains an asynchronous wrapper around the undocumented Minut
REST API used by the Minut web dashboard. The API endpoints and parameters
have been reverse engineered from public proof‑of‑concept code and the
community CLI tool【309709768529123†L230-L263】【56322294618823†L190-L255】. This client
implements the minimum functionality required to retrieve sensor data and
timeline events for Minut Point devices.

Authentication is performed using OAuth2. The client supports two ways of
obtaining tokens:

1. Providing a username and password. The `authenticate` class method will
   exchange these credentials for an access token, refresh token and user
   identifier. The client ID used here (`c33c3776f220cd90`) matches the one
   discovered in the proof‑of‑concept web page【309709768529123†L230-L263】.
2. Providing an access token, refresh token and user identifier directly. This
   is useful when copying tokens from the Minut web dashboard as described in
   the integration README.

Once initialised, the client exposes methods for fetching the list of devices,
retrieving the latest sensor reading for temperature, humidity and noise, and
getting a list of recent timeline events for each device. Token refresh is
attempted transparently on 401 responses when a refresh token is available.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


_LOGGER = logging.getLogger(__name__)


class MinutAPI:
    """Minimal asynchronous API wrapper for Minut devices."""

    BASE_URL = "https://api.minut.com/draft1"
    CLIENT_ID = "c33c3776f220cd90"  # client ID used by the Minut web dashboard

    def __init__(self, session: aiohttp.ClientSession, *, user_id: str, access_token: str, refresh_token: Optional[str] = None) -> None:
        self._session = session
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token

    @classmethod
    async def authenticate(cls, session: aiohttp.ClientSession, username: str, password: str) -> Tuple[str, str, str]:
        """Authenticate using username/password and return (user_id, access_token, refresh_token).

        This method sends a POST request to the `/auth/token` endpoint with the
        grant type set to `password` and uses the client ID that the Minut web
        dashboard uses. If authentication fails, it raises an exception.
        """
        url = f"{cls.BASE_URL}/auth/token"
        payload = {
            "client_id": cls.CLIENT_ID,
            "grant_type": "password",
            "username": username,
            "password": password,
        }
        _LOGGER.debug("Authenticating to Minut with username")
        async with session.post(url, data=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Authentication failed: HTTP {resp.status}: {text}")
            data = await resp.json()
            if "access_token" not in data or "refresh_token" not in data or "user_id" not in data:
                raise RuntimeError(f"Unexpected response from token endpoint: {data}")
            return data["user_id"], data["access_token"], data["refresh_token"]

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an HTTP request with automatic bearer token and optional refresh.

        If a 401 response is received and a refresh token is available, the
        client will attempt to refresh the access token once before
        re‑attempting the original request. If the second attempt also fails,
        the call will raise an exception.
        """
        url = f"{self.BASE_URL}{path}"
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"
        attempt = 0
        while True:
            async with self._session.request(method, url, headers=headers, **kwargs) as resp:
                if resp.status == 401 and self.refresh_token and attempt == 0:
                    _LOGGER.warning("Access token expired, attempting to refresh")
                    try:
                        await self._refresh_access_token()
                    except Exception as err:
                        _LOGGER.error("Failed to refresh access token: %s", err)
                        break
                    attempt += 1
                    # update Authorization header with new token
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    continue
                if resp.status >= 400:
                    text = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {text}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()

    async def _refresh_access_token(self) -> None:
        """Refresh the access token using the stored refresh token."""
        if not self.refresh_token:
            raise RuntimeError("No refresh token available")
        url = f"{self.BASE_URL}/auth/token"
        payload = {
            "client_id": self.CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        async with self._session.post(url, data=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"Token refresh failed: HTTP {resp.status}: {text}")
            data = await resp.json()
            _LOGGER.info("Refreshed Minut access token")
            self.access_token = data.get("access_token", self.access_token)
            # Update refresh token if the API rotated it
            self.refresh_token = data.get("refresh_token", self.refresh_token)

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Return a list of devices associated with the user.

        Each item in the returned list includes at minimum `id` and
        `description`. Additional fields may be present depending on the API
        version. The endpoint is `/devices` and requires a valid bearer token
        【56322294618823†L190-L255】.
        """
        data = await self._request("GET", "/devices")
        devices = data if isinstance(data, list) else data.get("devices", data)
        return devices

    async def _get_sensor_values(self, device_id: str, endpoint: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch raw sensor values from a specific device endpoint.

        Returns a list of dictionaries with at least `value` and `datetime` keys
        or None if the response does not match expectations.
        """
        data = await self._request("GET", f"/devices/{device_id}/{endpoint}")
        if isinstance(data, dict) and "values" in data:
            return data.get("values")
        # Some endpoints might return the array directly
        if isinstance(data, list):
            return data
        return None

    async def get_latest_sensor_value(self, device_id: str, sensor_type: str) -> Optional[float]:
        """Return the latest sensor reading for a given type.

        The supported types are "temperature", "humidity" and "noise". Noise is
        fetched from the `sound_avg_levels` endpoint. Temperature and humidity
        use endpoints with the same name. The response is expected to be a
        collection of time‑series values where the last item is the most recent
        【56322294618823†L190-L255】.
        """
        endpoint = sensor_type
        if sensor_type == "noise":
            endpoint = "sound_avg_levels"
        values = await self._get_sensor_values(device_id, endpoint)
        if not values:
            return None
        # Each value is a dict like {"value": 23.5, "datetime": "2023-09-28T09:00:00"}
        latest = values[-1]
        return latest.get("value")

    async def get_recent_events(self, since: timedelta = timedelta(minutes=2)) -> Dict[str, List[str]]:
        """Retrieve recent timeline events grouped by device ID.

        Fetches the user's timeline via `/timelines/me` and returns a mapping
        between device IDs and a list of event types that occurred within the
        given time window. The `since` parameter controls how far back events
        are considered recent. Events older than `now - since` are ignored.
        【56322294618823†L266-L294】 illustrates how the CLI fetches the timeline.
        """
        params = {"limit": 200}
        data = await self._request("GET", "/timelines/me", params=params)
        events_by_device: Dict[str, List[str]] = {}
        now = datetime.now(timezone.utc)
        if isinstance(data, list):
            timeline = data
        else:
            timeline = data.get("events", [])
        for event in timeline:
            event_type = event.get("type")
            device_id = event.get("device_id") or event.get("device", {}).get("id")
            timestamp_str = event.get("timestamp") or event.get("datetime")
            if not (event_type and device_id and timestamp_str):
                continue
            try:
                event_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                continue
            if now - event_time > since:
                # The timeline is ordered newest first; break once we encounter
                # events older than our window to minimise processing
                continue
            events_by_device.setdefault(str(device_id), []).append(str(event_type))
        return events_by_device