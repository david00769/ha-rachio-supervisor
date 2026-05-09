"""Coordinator scaffold for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_SITE_NAME,
    CONF_ZONE_COUNT,
    DOMAIN,
)
from .discovery import discover_linked_entities

TZ = ZoneInfo("UTC")


@dataclass(slots=True)
class SupervisorSnapshot:
    """Site-level public snapshot for the first runtime milestone."""

    health: str
    mode: str
    action_posture: str
    site_name: str
    linked_entry_title: str
    linked_entry_state: str
    rachio_config_entry_id: str
    rain_actuals_entity: str
    zone_count: int
    configured_zone_count: int
    active_zone_count: int
    active_schedule_count: int
    connectivity: str
    rain_state: str
    rain_delay_state: str
    standby_state: str
    actual_rain_value: str
    actual_rain_unit: str | None
    rain_actuals_status: str
    last_refresh: str
    notes: tuple[str, ...]
    discovered_entities: dict[str, object]


class RachioSupervisorCoordinator(DataUpdateCoordinator[SupervisorSnapshot]):
    """Scaffold coordinator for the public seed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.entry = entry

    async def _async_update_data(self) -> SupervisorSnapshot:
        """Return the current site-level supervision snapshot."""
        data = {**self.entry.data, **self.entry.options}
        observe_first = data.get(CONF_OBSERVE_FIRST, True)
        mode = "observe_only" if observe_first else "manual_review"
        moisture_mode = data.get(CONF_ALLOW_MOISTURE_WRITE_BACK, False)
        action_posture = (
            "per_zone_opt_in_with_write_back_available"
            if moisture_mode
            else "per_zone_opt_in"
        )
        linked_entry = self.hass.config_entries.async_get_entry(
            data.get(CONF_RACHIO_CONFIG_ENTRY_ID, "")
        )
        linked_entry_title = linked_entry.title if linked_entry else "missing"
        linked_entry_state = linked_entry.state.value if linked_entry else "missing"
        linked_entities = discover_linked_entities(
            self.hass,
            data.get(CONF_RACHIO_CONFIG_ENTRY_ID, ""),
        )
        notes: list[str] = []

        def state_value(entity_id: str | None) -> str:
            if not entity_id:
                return "missing"
            state = self.hass.states.get(entity_id)
            if state is None:
                return "missing"
            return str(state.state)

        def active_count(entity_ids: tuple[str, ...]) -> int:
            count = 0
            for entity_id in entity_ids:
                state = self.hass.states.get(entity_id)
                if state and state.state == "on":
                    count += 1
            return count

        rain_state_obj = self.hass.states.get(data.get(CONF_RAIN_ACTUALS_ENTITY, ""))
        if rain_state_obj is None:
            actual_rain_value = "unavailable"
            actual_rain_unit = None
            rain_actuals_status = "missing"
            notes.append("Actual rain entity is missing or unavailable.")
        elif rain_state_obj.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            actual_rain_value = str(rain_state_obj.state)
            actual_rain_unit = rain_state_obj.attributes.get("unit_of_measurement")
            rain_actuals_status = "unavailable"
            notes.append("Actual rain entity is present but not reporting a usable value.")
        else:
            actual_rain_value = str(rain_state_obj.state)
            actual_rain_unit = rain_state_obj.attributes.get("unit_of_measurement")
            rain_actuals_status = "ok"

        connectivity = state_value(linked_entities.connectivity_entity_id)
        rain_state = state_value(linked_entities.rain_entity_id)
        rain_delay_state = state_value(linked_entities.rain_delay_entity_id)
        standby_state = state_value(linked_entities.standby_entity_id)

        if linked_entry is None:
            notes.append("Linked Home Assistant Rachio config entry was not found.")
        elif linked_entry.state != ConfigEntryState.LOADED:
            notes.append(f"Linked Home Assistant Rachio entry is {linked_entry.state.value}.")
        if connectivity == "missing":
            notes.append("Connectivity entity could not be discovered from the linked Rachio entry.")
        if not linked_entities.zone_switches:
            notes.append("No zone switches were discovered from the linked Rachio entry.")

        if linked_entry and linked_entry.state == ConfigEntryState.LOADED and rain_actuals_status == "ok":
            health = "healthy"
        elif linked_entry and linked_entry.state in {
            ConfigEntryState.LOADED,
            ConfigEntryState.SETUP_IN_PROGRESS,
            ConfigEntryState.NOT_LOADED,
        }:
            health = "degraded"
        else:
            health = "unavailable"

        return SupervisorSnapshot(
            health=health,
            mode=mode,
            action_posture=action_posture,
            site_name=data.get(CONF_SITE_NAME, self.entry.title),
            linked_entry_title=linked_entry_title,
            linked_entry_state=linked_entry_state,
            rachio_config_entry_id=data.get(CONF_RACHIO_CONFIG_ENTRY_ID, ""),
            rain_actuals_entity=data.get(CONF_RAIN_ACTUALS_ENTITY, ""),
            zone_count=int(data.get(CONF_ZONE_COUNT, 0)),
            configured_zone_count=len(linked_entities.zone_switches),
            active_zone_count=active_count(linked_entities.zone_switches),
            active_schedule_count=active_count(linked_entities.schedule_switches),
            connectivity=connectivity,
            rain_state=rain_state,
            rain_delay_state=rain_delay_state,
            standby_state=standby_state,
            actual_rain_value=actual_rain_value,
            actual_rain_unit=actual_rain_unit,
            rain_actuals_status=rain_actuals_status,
            last_refresh=datetime.now(tz=TZ).isoformat(),
            notes=tuple(notes),
            discovered_entities={
                "connectivity": linked_entities.connectivity_entity_id,
                "rain": linked_entities.rain_entity_id,
                "rain_delay": linked_entities.rain_delay_entity_id,
                "standby": linked_entities.standby_entity_id,
                "zone_switches": list(linked_entities.zone_switches),
                "schedule_switches": list(linked_entities.schedule_switches),
                "entity_count": len(linked_entities.all_entities),
            },
        )
