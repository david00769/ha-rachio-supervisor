"""Rachio Supervisor for Home Assistant."""

from __future__ import annotations

from collections.abc import Callable

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    DOMAIN,
    SERVICE_ACKNOWLEDGE_RECOMMENDATION,
    SERVICE_CLEAR_FLOW_ALERT_REVIEW,
    SERVICE_CLEAR_RECOMMENDATION_ACKNOWLEDGEMENT,
    SERVICE_EVALUATE_NOW,
    SERVICE_WRITE_MOISTURE_NOW,
)
from .coordinator import RachioSupervisorCoordinator, ScheduleSnapshot
from .rachio_api import RachioClient

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def _async_options_update_listener(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Reload the entry after options change so coordinator state is rebuilt."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_handle_evaluate_now(hass: HomeAssistant, call: ServiceCall) -> None:
    """Refresh the loaded supervisor entries immediately."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("No Rachio Supervisor entries are loaded.")

    for coordinator in coordinators.values():
        await coordinator.async_request_refresh()


def _find_schedule_target(
    coordinators: dict[str, RachioSupervisorCoordinator],
    schedule_name: str | None,
    schedule_entity_id: str | None,
    site_name: str | None,
) -> tuple[RachioSupervisorCoordinator, ScheduleSnapshot]:
    """Resolve one schedule snapshot across loaded coordinators."""
    matches: list[tuple[RachioSupervisorCoordinator, ScheduleSnapshot]] = []
    for coordinator in coordinators.values():
        if site_name and coordinator.data.site_name != site_name:
            continue
        for schedule in coordinator.data.schedule_snapshots:
            if schedule_entity_id and schedule.schedule_entity_id == schedule_entity_id:
                matches.append((coordinator, schedule))
            elif schedule_name and schedule.name == schedule_name:
                matches.append((coordinator, schedule))
    if not matches:
        raise HomeAssistantError("No matching Rachio Supervisor schedule was found.")
    if len(matches) > 1:
        raise HomeAssistantError(
            "Multiple schedules matched. Provide site_name to disambiguate."
        )
    return matches[0]


async def _async_handle_write_moisture_now(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Write the currently mapped moisture value into one resolved Rachio zone."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("No Rachio Supervisor entries are loaded.")

    schedule_name = (
        str(call.data["schedule_name"]) if call.data.get("schedule_name") else None
    )
    schedule_entity_id = (
        str(call.data["schedule_entity_id"])
        if call.data.get("schedule_entity_id")
        else None
    )
    if not schedule_name and not schedule_entity_id:
        raise HomeAssistantError(
            "Provide either schedule_entity_id or schedule_name."
        )
    site_name = call.data.get("site_name")
    coordinator, schedule = _find_schedule_target(
        coordinators,
        schedule_name,
        schedule_entity_id,
        site_name,
    )

    data = {**coordinator.entry.data, **coordinator.entry.options}
    if not data.get(CONF_ALLOW_MOISTURE_WRITE_BACK, False):
        coordinator.record_moisture_write(
            status="rejected_write_back_disabled",
            schedule_name=schedule.name,
            moisture_value=schedule.moisture_value,
        )
        raise HomeAssistantError(
            "Moisture write-back is not enabled for this Rachio Supervisor entry."
        )
    if not schedule.controller_zone_id:
        coordinator.record_moisture_write(
            status="rejected_zone_unresolved",
            schedule_name=schedule.name,
            moisture_value=schedule.moisture_value,
        )
        raise HomeAssistantError("The selected schedule does not resolve to a Rachio zone.")
    if schedule.moisture_value is None:
        coordinator.record_moisture_write(
            status="rejected_missing_moisture_value",
            schedule_name=schedule.name,
            moisture_value=schedule.moisture_value,
        )
        raise HomeAssistantError(
            "The selected schedule does not have a usable mapped moisture value."
        )
    try:
        moisture_percent = float(schedule.moisture_value)
    except (TypeError, ValueError) as exc:
        coordinator.record_moisture_write(
            status="rejected_non_numeric_moisture_value",
            schedule_name=schedule.name,
            moisture_value=schedule.moisture_value,
        )
        raise HomeAssistantError(
            "The selected schedule does not have a numeric mapped moisture value."
        ) from exc

    linked_entry = hass.config_entries.async_get_entry(coordinator.data.rachio_config_entry_id)
    if linked_entry is None:
        coordinator.record_moisture_write(
            status="rejected_missing_linked_entry",
            schedule_name=schedule.name,
            moisture_value=schedule.moisture_value,
        )
        raise HomeAssistantError("The linked Home Assistant Rachio entry was not found.")
    api_key = linked_entry.data.get(CONF_API_KEY)
    if not api_key:
        coordinator.record_moisture_write(
            status="rejected_missing_api_key",
            schedule_name=schedule.name,
            moisture_value=schedule.moisture_value,
        )
        raise HomeAssistantError("The linked Home Assistant Rachio entry has no API key.")

    client = RachioClient(str(api_key))
    await hass.async_add_executor_job(
        client.set_zone_moisture_percent,
        schedule.controller_zone_id,
        max(0.0, min(100.0, moisture_percent)),
    )
    coordinator.record_moisture_write(
        status="written",
        schedule_name=schedule.name,
        moisture_value=f"{max(0.0, min(100.0, moisture_percent)):g}",
    )
    await coordinator.async_request_refresh()


async def _async_handle_recommendation_ack(
    hass: HomeAssistant,
    call: ServiceCall,
    *,
    acknowledged: bool,
) -> None:
    """Set or clear runtime acknowledgement for one recommendation."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("No Rachio Supervisor entries are loaded.")

    schedule_name = (
        str(call.data["schedule_name"]) if call.data.get("schedule_name") else None
    )
    schedule_entity_id = (
        str(call.data["schedule_entity_id"])
        if call.data.get("schedule_entity_id")
        else None
    )
    if not schedule_name and not schedule_entity_id:
        raise HomeAssistantError(
            "Provide either schedule_entity_id or schedule_name."
        )
    site_name = call.data.get("site_name")
    coordinator, schedule = _find_schedule_target(
        coordinators,
        schedule_name,
        schedule_entity_id,
        site_name,
    )
    coordinator.set_recommendation_acknowledged(
        rule_id=schedule.rule_id,
        acknowledged=acknowledged,
    )
    await coordinator.async_request_refresh()


async def _async_handle_acknowledge_recommendation(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Mark one current recommendation as reviewed."""
    await _async_handle_recommendation_ack(
        hass,
        call,
        acknowledged=True,
    )


async def _async_handle_clear_recommendation_acknowledgement(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Return one recommendation to the active review queue."""
    await _async_handle_recommendation_ack(
        hass,
        call,
        acknowledged=False,
    )


async def _async_handle_clear_flow_alert_review(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Clear current Supervisor-side flow alert review state."""
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("No Rachio Supervisor entries are loaded.")

    site_name = call.data.get("site_name")
    rule_id = str(call.data["rule_id"]) if call.data.get("rule_id") else None
    matched = [
        coordinator
        for coordinator in coordinators.values()
        if not site_name or coordinator.data.site_name == site_name
    ]
    if not matched:
        raise HomeAssistantError("No matching Rachio Supervisor site was found.")
    if len(matched) > 1 and not site_name:
        raise HomeAssistantError("Multiple sites are loaded. Provide site_name.")

    for coordinator in matched:
        try:
            coordinator.clear_flow_alert_review(rule_id=rule_id)
        except ValueError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await coordinator.async_request_refresh()


@callback
def _async_register_services(hass: HomeAssistant) -> Callable[[], None]:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_EVALUATE_NOW):
        return lambda: None

    async def _handle_ack(call: ServiceCall) -> None:
        await _async_handle_acknowledge_recommendation(hass, call)

    async def _handle_clear_ack(call: ServiceCall) -> None:
        await _async_handle_clear_recommendation_acknowledgement(hass, call)

    async def _handle_clear_flow_alert_review(call: ServiceCall) -> None:
        await _async_handle_clear_flow_alert_review(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_EVALUATE_NOW,
        _async_handle_evaluate_now,
        schema=vol.Schema({vol.Optional("entity_id"): cv.entity_ids}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_WRITE_MOISTURE_NOW,
        _async_handle_write_moisture_now,
        schema=vol.Schema(
            {
                vol.Optional("schedule_name"): cv.string,
                vol.Optional("schedule_entity_id"): cv.entity_id,
                vol.Optional("site_name"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ACKNOWLEDGE_RECOMMENDATION,
        _handle_ack,
        schema=vol.Schema(
            {
                vol.Optional("schedule_name"): cv.string,
                vol.Optional("schedule_entity_id"): cv.entity_id,
                vol.Optional("site_name"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_RECOMMENDATION_ACKNOWLEDGEMENT,
        _handle_clear_ack,
        schema=vol.Schema(
            {
                vol.Optional("schedule_name"): cv.string,
                vol.Optional("schedule_entity_id"): cv.entity_id,
                vol.Optional("site_name"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_FLOW_ALERT_REVIEW,
        _handle_clear_flow_alert_review,
        schema=vol.Schema(
            {
                vol.Optional("rule_id"): cv.string,
                vol.Optional("site_name"): cv.string,
            }
        ),
    )

    def _remove() -> None:
        hass.services.async_remove(DOMAIN, SERVICE_EVALUATE_NOW)
        hass.services.async_remove(DOMAIN, SERVICE_WRITE_MOISTURE_NOW)
        hass.services.async_remove(DOMAIN, SERVICE_ACKNOWLEDGE_RECOMMENDATION)
        hass.services.async_remove(
            DOMAIN, SERVICE_CLEAR_RECOMMENDATION_ACKNOWLEDGEMENT
        )
        hass.services.async_remove(DOMAIN, SERVICE_CLEAR_FLOW_ALERT_REVIEW)

    return _remove


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[f"{DOMAIN}_remove_services"] = _async_register_services(hass)

    coordinator = RachioSupervisorCoordinator(hass=hass, entry=entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_options_update_listener))
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
