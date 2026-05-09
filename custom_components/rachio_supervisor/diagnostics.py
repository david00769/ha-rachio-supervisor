"""Diagnostics support for Rachio Supervisor."""

from __future__ import annotations

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
        "snapshot": coordinator.data.__dict__,
        "notes": [
            "This diagnostics payload reflects the public scaffold stage.",
            "Full Rachio event and moisture evidence plumbing is not implemented yet.",
        ],
    }

