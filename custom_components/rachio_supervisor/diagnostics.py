"""Diagnostics support for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION


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
        "entry_data": entry.data,
        "entry_options": entry.options,
        "snapshot": asdict(coordinator.data),
        "notes": [
            "This diagnostics payload reflects the first runtime milestone.",
            "It links to an existing Home Assistant Rachio entry and publishes site-level evidence.",
            "Full Rachio event history, catch-up policy, and moisture write-back flows are still pending.",
        ],
    }
