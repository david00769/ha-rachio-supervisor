"""Diagnostics support for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_WEATHER_UNDERGROUND_API_KEY, DOMAIN, VERSION

REDACTED = "**REDACTED**"


def _redact_config(data: dict) -> dict:
    """Return config data safe for diagnostics export."""
    redacted = dict(data or {})
    if redacted.get(CONF_WEATHER_UNDERGROUND_API_KEY):
        redacted[CONF_WEATHER_UNDERGROUND_API_KEY] = REDACTED
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "domain": DOMAIN,
        "version": VERSION,
        "title": entry.title,
        "entry_data": _redact_config(entry.data),
        "entry_options": _redact_config(entry.options),
        "snapshot": asdict(coordinator.data),
        "notes": [
            "This diagnostics payload reflects the current public runtime milestone.",
            "It links to an existing Home Assistant Rachio entry and publishes site-level evidence plus supervision state.",
            "Automatic irrigation behavior remains intentionally narrow and opt-in.",
            "Moisture auto-write updates Rachio moisture estimates only; it does not start watering.",
            "Rachio weather-source hints are diagnostic only; forecast precipitation is not treated as observed rainfall.",
            "Photo import status is concrete when the import option is enabled; disabled means the option is off.",
        ],
    }
