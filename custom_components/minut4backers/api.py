from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from aiohttp import ClientResponseError

BASE_URL = "https://api.minut.com"
OAUTH_TOKEN_URL = f"{BASE_URL}/v1/oauth/token"
# These are the “web dashboard” style endpoints that work without official API access:
DRAFT_DEVICES_URL = f"{BASE_URL}/draft1/devices"
DRAFT_DEVICE_TIMELINE_URL = f"{BASE_URL}/draft1/device/{{device_id}}/timeline"
# Best-effort “latest” reads; if any of these 404 we’ll fall back to timeline-only
DRAFT_TEMP_VALUES_URL = f"{BASE_URL}/draft1/device/{{device_id}}/temperature/values?limit=1"
DRAFT_HUMID_VALUES_URL = f"{BASE_URL}/draft1/device/{{device_id}}/humidity/values?limit=1"
DRAFT_SOUND_AVG_URL = f"{BASE_URL}/draft1/device/{{device_id}}/sound/avg_levels?limit=1"

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20)

@dataclass
class Tokens:
    access_token: str
    refresh_token: Optional[str] = None
    user_id: Optional[str] = None

class MinutAuthError(Exception):
    """Auth/permission problems (401/403)."""

class MinutRateLimitError(Exception):
    """429 Too Many Requests."""

class MinutConnectError(Exception):
    """Network/downstream problems (timeouts, DNS, 5xx)."""

class MinutAPI:
    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def password_login(self, username: str, password: str) -> Tokens:
        """
        Emulates the dashboard password grant:
        POST /v1/oauth/token  (x-www-form-urlencoded)
        grant_type=password&username=...&password=...
        """
        data = {
            "grant_type": "password",
            "username": username,
            "password": password,
        }
        try:
            async with self._session.post(
                OAUTH_TOKEN_URL,
                data=data,
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise MinutAuthError("invalid_auth")
                if resp.status == 429:
                    raise MinutRateLimitError("rate_limited")
                resp.raise_for_status()
                js = await resp.json()
        except ClientResponseError as e:
            if 500 <= e.status < 600:
                raise MinutConnectError("server_error") from e
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            raise MinutConnectError("cannot_connect") from e

        return Tokens(
            access_token=js.get("access_token", ""),
            refresh_token=js.get("refresh_token"),
            user_id=str(js.get("user_id")) if js.get("user_id") is not None else None,
        )

    async def _auth_headers(self, tokens: Tokens) -> Dict[str, str]:
        return {"Authorization": f"Bearer {tokens.access_token}", "Accept": "application/json"}

    async def get_devices(self, tokens: Tokens) -> List[Dict[str, Any]]:
        try:
            async with self._session.get(
                DRAFT_DEVICES_URL,
                headers=await self._auth_headers(tokens),
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise MinutAuthError("invalid_auth")
                if resp.status == 429:
                    raise MinutRateLimitError("rate_limited")
                resp.raise_for_status()
                js = await resp.json()
                # Expect list of devices (dashboard shape)
                return js if isinstance(js, list) else js.get("devices", [])
        except ClientResponseError as e:
            if 500 <= e.status < 600:
                raise MinutConnectError("server_error") from e
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError) as e:
            raise MinutConnectError("cannot_connect") from e

    async def get_latest_values(self, tokens: Tokens, device_id: str) -> Dict[str, Optional[float]]:
        """
        Try per-sensor endpoints; if missing, return None for that metric.
        """
        headers = await self._auth_headers(tokens)
        async def fetch_float(url: str) -> Optional[float]:
            try:
                async with self._session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT) as resp:
                    if resp.status in (401, 403):
                        raise MinutAuthError("invalid_auth")
                    if resp.status == 404:
                        return None
                    if resp.status == 429:
                        raise MinutRateLimitError("rate_limited")
                    resp.raise_for_status()
                    js = await resp.json()
                    # accept [{value: x}] or {values:[{value:x}]}
                    if isinstance(js, list) and js:
                        v = js[-1].get("value")
                        return float(v) if v is not None else None
                    if isinstance(js, dict):
                        vals = js.get("values") or js.get("data") or []
                        if vals:
                            v = vals[-1].get("value")
                            return float(v) if v is not None else None
                    return None
            except ClientResponseError as e:
                if 500 <= e.status < 600:
                    raise MinutConnectError("server_error") from e
                raise
            except (asyncio.TimeoutError, aiohttp.ClientError):
                # Treat network hiccup as missing (coordinator will try again)
                return None

        temperature = await fetch_float(DRAFT_TEMP_VALUES_URL.format(device_id=device_id))
        humidity = await fetch_float(DRAFT_HUMID_VALUES_URL.format(device_id=device_id))
        noise = await fetch_float(DRAFT_SOUND_AVG_URL.format(device_id=device_id))
        return {"temperature": temperature, "humidity": humidity, "noise": noise}

    async def get_recent_events(
        self, tokens: Tokens, device_id: str, within: timedelta = timedelta(minutes=2)
    ) -> List[Dict[str, Any]]:
        """
        Pull the latest timeline events and keep those that happened within `within`.
        Events of interest include:
          - activity_detected (motion)
          - alarm_heard, avg_sound_high, sound_level_dropped_normal (noise/alarm)
          - tamper, short_button_press, battery_low, device_online/offline etc.
        """
        headers = await self._auth_headers(tokens)
        now = datetime.now(timezone.utc)

        try:
            async with self._session.get(
                f"{DRAFT_DEVICE_TIMELINE_URL.format(device_id=device_id)}?limit=20",
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            ) as resp:
                if resp.status in (401, 403):
                    raise MinutAuthError("invalid_auth")
                if resp.status == 429:
                    raise MinutRateLimitError("rate_limited")
                if resp.status == 404:
                    return []
                resp.raise_for_status()
                js = await resp.json()
        except ClientResponseError as e:
            if 500 <= e.status < 600:
                raise MinutConnectError("server_error") from e
            raise
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return []

        events = js if isinstance(js, list) else js.get("events", [])
        recent: List[Dict[str, Any]] = []
        for ev in events:
            ts = ev.get("timestamp") or ev.get("time") or ev.get("created_at")
            try:
                when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            except Exception:
                continue
            if now - when <= within:
                recent.append(ev)
        return recent