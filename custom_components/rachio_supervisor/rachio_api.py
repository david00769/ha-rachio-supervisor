"""Thin Rachio public API adapter for the supervisor."""

from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request
from typing import Any

PERSON_INFO_URL = "https://api.rach.io/1/public/person/info"
PERSON_URL = "https://api.rach.io/1/public/person/{person_id}"
DEVICE_EVENTS_URL = (
    "https://api.rach.io/1/public/device/{device_id}/event"
    "?startTime={start_ms}&endTime={end_ms}"
)
DEVICE_WEBHOOKS_URL = "https://api.rach.io/1/public/notification/{device_id}/webhook"


class RachioClientError(RuntimeError):
    """Raised when the Rachio public API returns an error."""


class RachioClient:
    """Minimal reusable adapter over the Rachio public REST API."""

    def __init__(self, token: str) -> None:
        self._token = token

    def _http_json(self, url: str) -> Any:
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RachioClientError(f"GET {url} failed: {exc.code} {detail[:300]}") from exc
        except urllib.error.URLError as exc:
            raise RachioClientError(f"GET {url} failed: {exc}") from exc
        return json.loads(payload) if payload else None

    def get_person_info(self) -> dict[str, Any]:
        return self._http_json(PERSON_INFO_URL)

    def get_person_detail(self, person_id: str) -> dict[str, Any]:
        return self._http_json(PERSON_URL.format(person_id=person_id))

    def list_person_devices(self) -> list[dict[str, Any]]:
        person = self.get_person_info()
        person_detail = self.get_person_detail(person["id"])
        devices = person_detail.get("devices", [])
        return devices if isinstance(devices, list) else []

    def list_device_webhooks(self, device_id: str) -> list[dict[str, Any]]:
        data = self._http_json(DEVICE_WEBHOOKS_URL.format(device_id=device_id))
        return data if isinstance(data, list) else []

    def list_device_events(
        self,
        device_id: str,
        *,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[dict[str, Any]]:
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        data = self._http_json(
            DEVICE_EVENTS_URL.format(device_id=device_id, start_ms=start_ms, end_ms=end_ms)
        )
        return data if isinstance(data, list) else []
