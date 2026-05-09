"""Rachio Supervisor for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, SERVICE_EVALUATE_NOW
from .coordinator import RachioSupervisorCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def _async_handle_evaluate_now(hass: HomeAssistant, call: ServiceCall) -> None:
    """Refresh the loaded supervisor entries immediately."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("No Rachio Supervisor entries are loaded.")

    for coordinator in coordinators.values():
        await coordinator.async_request_refresh()


@callback
def _async_register_services(hass: HomeAssistant) -> Callable[[], None]:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_EVALUATE_NOW):
        return lambda: None

    hass.services.async_register(
        DOMAIN,
        SERVICE_EVALUATE_NOW,
        _async_handle_evaluate_now,
        schema=vol.Schema({vol.Optional("entity_id"): cv.entity_ids}),
    )

    def _remove() -> None:
        hass.services.async_remove(DOMAIN, SERVICE_EVALUATE_NOW)

    return _remove


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[f"{DOMAIN}_remove_services"] = _async_register_services(hass)

    coordinator = RachioSupervisorCoordinator(hass=hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            remove = hass.data.pop(f"{DOMAIN}_remove_services", None)
            if remove:
                remove()
            hass.data.pop(DOMAIN, None)
    return unload_ok
