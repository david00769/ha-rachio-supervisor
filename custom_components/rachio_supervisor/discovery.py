"""Discovery helpers for linking to the built-in Rachio integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import RACHIO_DOMAIN


@dataclass(frozen=True, slots=True)
class ScheduleEntityRef:
    """Linked schedule entity metadata from the built-in Rachio integration."""

    entity_id: str
    label: str
    unique_id: str | None


@dataclass(frozen=True, slots=True)
class ZoneEntityRef:
    """Linked zone entity metadata from the built-in Rachio integration."""

    entity_id: str
    label: str
    unique_id: str | None


@dataclass(frozen=True, slots=True)
class LinkedRachioEntities:
    """Grouped Rachio entities discovered from a linked config entry."""

    connectivity_entity_id: str | None
    rain_entity_id: str | None
    rain_delay_entity_id: str | None
    standby_entity_id: str | None
    zone_switches: tuple[str, ...]
    schedule_switches: tuple[str, ...]
    zone_entities: tuple[ZoneEntityRef, ...]
    schedule_entities: tuple[ScheduleEntityRef, ...]
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
    def _entry_matches_config_entry(entry: er.RegistryEntry) -> bool:
        """Return True when the registry row belongs to the linked Rachio entry."""
        config_entry_ids = getattr(entry, "config_entry_ids", None)
        if config_entry_ids is not None:
            return rachio_config_entry_id in config_entry_ids
        return getattr(entry, "config_entry_id", None) == rachio_config_entry_id

    entries = [
        entry
        for entry in registry.entities.values()
        if _entry_matches_config_entry(entry)
    ]

    connectivity_entity_id = None
    rain_entity_id = None
    rain_delay_entity_id = None
    standby_entity_id = None
    zone_switches: list[str] = []
    schedule_switches: list[str] = []
    zone_entities: list[ZoneEntityRef] = []
    schedule_entities: list[ScheduleEntityRef] = []
    all_entities: list[str] = []

    for entry in entries:
        if entry.disabled_by is not None:
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
                    schedule_entities.append(
                        ScheduleEntityRef(
                            entity_id=entity_id,
                            label=entry.original_name or entity_id,
                            unique_id=entry.unique_id,
                        )
                    )
                else:
                    zone_switches.append(entity_id)
                    zone_entities.append(
                        ZoneEntityRef(
                            entity_id=entity_id,
                            label=entry.original_name or entity_id,
                            unique_id=entry.unique_id,
                        )
                    )

    return LinkedRachioEntities(
        connectivity_entity_id=connectivity_entity_id,
        rain_entity_id=rain_entity_id,
        rain_delay_entity_id=rain_delay_entity_id,
        standby_entity_id=standby_entity_id,
        zone_switches=tuple(sorted(zone_switches)),
        schedule_switches=tuple(sorted(schedule_switches)),
        zone_entities=tuple(
            sorted(zone_entities, key=lambda entity: entity.label.lower())
        ),
        schedule_entities=tuple(
            sorted(schedule_entities, key=lambda entity: entity.label.lower())
        ),
        all_entities=tuple(sorted(all_entities)),
    )


def schedule_entity_options(
    hass: HomeAssistant,
    rachio_config_entry_id: str,
) -> list[tuple[str, str]]:
    """Return discovered Rachio schedule entities as config-flow options."""
    linked = discover_linked_entities(hass, rachio_config_entry_id)
    return [(entity.entity_id, entity.label) for entity in linked.schedule_entities]
