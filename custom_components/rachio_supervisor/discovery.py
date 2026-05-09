"""Discovery helpers for linking to the built-in Rachio integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import RACHIO_DOMAIN


@dataclass(frozen=True, slots=True)
class LinkedRachioEntities:
    """Grouped Rachio entities discovered from a linked config entry."""

    connectivity_entity_id: str | None
    rain_entity_id: str | None
    rain_delay_entity_id: str | None
    standby_entity_id: str | None
    zone_switches: tuple[str, ...]
    schedule_switches: tuple[str, ...]
    all_entities: tuple[str, ...]


def rachio_config_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return configured Rachio config entries."""
    return [
        entry
        for entry in hass.config_entries.async_entries(RACHIO_DOMAIN)
        if entry.state
        in {
            ConfigEntryState.LOADED,
            ConfigEntryState.NOT_LOADED,
            ConfigEntryState.SETUP_IN_PROGRESS,
        }
    ]


def rachio_entry_options(hass: HomeAssistant) -> list[tuple[str, str]]:
    """Return config-flow options as (value, label)."""
    options: list[tuple[str, str]] = []
    for entry in rachio_config_entries(hass):
        label = entry.title or entry.entry_id
        if entry.state not in {ConfigEntryState.LOADED, ConfigEntryState.NOT_LOADED}:
            label = f"{label} ({entry.state.value})"
        options.append((entry.entry_id, label))
    return options


def discover_linked_entities(
    hass: HomeAssistant,
    rachio_config_entry_id: str,
) -> LinkedRachioEntities:
    """Discover the relevant linked Rachio entities from the entity registry."""
    registry = er.async_get(hass)
    entries = [
        entry
        for entry in registry.entities.values()
        if rachio_config_entry_id in entry.config_entry_ids
    ]

    connectivity_entity_id = None
    rain_entity_id = None
    rain_delay_entity_id = None
    standby_entity_id = None
    zone_switches: list[str] = []
    schedule_switches: list[str] = []
    all_entities: list[str] = []

    for entry in entries:
        if entry.disabled:
            continue
        entity_id = entry.entity_id
        all_entities.append(entity_id)

        if entity_id.startswith("binary_sensor."):
            if "connectivity" in entity_id:
                connectivity_entity_id = entity_id
            elif entity_id.endswith("_rain") or "rain" in entity_id:
                rain_entity_id = entity_id
        elif entity_id.startswith("switch."):
            if entity_id.endswith("_rain_delay") or "rain_delay" in entity_id:
                rain_delay_entity_id = entity_id
            elif entity_id.endswith("_standby") or "standby" in entity_id:
                standby_entity_id = entity_id
            else:
                unique_id = (entry.unique_id or "").lower()
                if "schedule" in unique_id:
                    schedule_switches.append(entity_id)
                else:
                    zone_switches.append(entity_id)

    return LinkedRachioEntities(
        connectivity_entity_id=connectivity_entity_id,
        rain_entity_id=rain_entity_id,
        rain_delay_entity_id=rain_delay_entity_id,
        standby_entity_id=standby_entity_id,
        zone_switches=tuple(sorted(zone_switches)),
        schedule_switches=tuple(sorted(schedule_switches)),
        all_entities=tuple(sorted(all_entities)),
    )
