"""Sensor platform for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RachioSupervisorCoordinator, SupervisorSnapshot
from .entity import RachioSupervisorEntity


@dataclass(frozen=True, kw_only=True)
class RachioSupervisorSensorDescription(SensorEntityDescription):
    """Description for scaffold sensors."""

    value_fn: Callable[[SupervisorSnapshot], str]


DESCRIPTIONS = (
    RachioSupervisorSensorDescription(
        key="health",
        translation_key="health",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.health,
    ),
    RachioSupervisorSensorDescription(
        key="mode",
        translation_key="mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.mode,
    ),
    RachioSupervisorSensorDescription(
        key="linked_rachio_entry",
        translation_key="linked_rachio_entry",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.linked_entry_title,
    ),
    RachioSupervisorSensorDescription(
        key="action_posture",
        translation_key="action_posture",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.action_posture,
    ),
    RachioSupervisorSensorDescription(
        key="rain_actuals_source",
        translation_key="rain_actuals_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.rain_actuals_entity or "unconfigured",
    ),
    RachioSupervisorSensorDescription(
        key="actual_rain_24h",
        translation_key="actual_rain_24h",
        value_fn=lambda data: data.actual_rain_value,
    ),
    RachioSupervisorSensorDescription(
        key="last_run",
        translation_key="last_run",
        value_fn=lambda data: data.last_run_summary,
    ),
    RachioSupervisorSensorDescription(
        key="last_skip",
        translation_key="last_skip",
        value_fn=lambda data: data.last_skip_summary,
    ),
    RachioSupervisorSensorDescription(
        key="active_zone_count",
        translation_key="active_zone_count",
        value_fn=lambda data: str(data.active_zone_count),
    ),
    RachioSupervisorSensorDescription(
        key="configured_zone_count",
        translation_key="configured_zone_count",
        value_fn=lambda data: str(data.configured_zone_count),
    ),
    RachioSupervisorSensorDescription(
        key="last_refresh",
        translation_key="last_refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_refresh,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scaffold sensors."""
    coordinator: RachioSupervisorCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [RachioSupervisorSensor(coordinator, description) for description in DESCRIPTIONS]
    entities.extend(
        RachioSupervisorScheduleSensor(coordinator, schedule, suffix, label)
        for schedule in coordinator.data.schedule_snapshots
        for suffix, label in (
            ("status", "Status"),
            ("reason", "Reason"),
            ("catch_up_candidate", "Catch-up candidate"),
        )
    )
    async_add_entities(entities)


class RachioSupervisorSensor(RachioSupervisorEntity, SensorEntity):
    """Scaffold sensor entity."""

    entity_description: RachioSupervisorSensorDescription

    def __init__(
        self,
        coordinator: RachioSupervisorCoordinator,
        description: RachioSupervisorSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> str:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return contextual attributes for the current sensor."""
        data = self.coordinator.data
        if self.entity_description.key == "health":
            return {
                "linked_entry_title": data.linked_entry_title,
                "linked_entry_state": data.linked_entry_state,
                "connectivity": data.connectivity,
                "rain_state": data.rain_state,
                "rain_delay_state": data.rain_delay_state,
                "standby_state": data.standby_state,
                "controller_name": data.controller_name,
                "controller_id": data.controller_id,
                "webhook_count": data.webhook_count,
                "notes": list(data.notes),
            }
        if self.entity_description.key == "actual_rain_24h":
            return {
                "unit_of_measurement": data.actual_rain_unit,
                "status": data.rain_actuals_status,
                "source_entity": data.rain_actuals_entity,
            }
        if self.entity_description.key == "last_run":
            return {
                "last_run_at": data.last_run_at,
                "controller_name": data.controller_name,
            }
        if self.entity_description.key == "last_skip":
            return {
                "last_skip_at": data.last_skip_at,
                "controller_name": data.controller_name,
            }
        if self.entity_description.key == "configured_zone_count":
            return {
                "expected_zone_count": data.zone_count,
                "discovered_schedule_count": data.active_schedule_count,
                "discovered_entities": data.discovered_entities,
            }
        return None


class RachioSupervisorScheduleSensor(RachioSupervisorEntity, SensorEntity):
    """Per-schedule sensor entity."""

    def __init__(
        self,
        coordinator: RachioSupervisorCoordinator,
        schedule: ScheduleSnapshot,
        suffix: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._schedule_rule_id = schedule.rule_id
        self._suffix = suffix
        self._attr_name = f"{schedule.name} {label}"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{schedule.rule_id}_{suffix}"
        )

    def _current(self) -> ScheduleSnapshot | None:
        for schedule in self.coordinator.data.schedule_snapshots:
            if schedule.rule_id == self._schedule_rule_id:
                return schedule
        return None

    @property
    def native_value(self) -> str:
        """Return the current schedule value."""
        schedule = self._current()
        if schedule is None:
            return "unavailable"
        return str(getattr(schedule, self._suffix))

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return contextual attributes for the current schedule sensor."""
        schedule = self._current()
        if schedule is None:
            return None
        return {
            "rule_id": schedule.rule_id,
            "schedule_name": schedule.name,
            "last_run_at": schedule.last_run_at,
            "last_skip_at": schedule.last_skip_at,
            "observed_mm": schedule.observed_mm,
            "threshold_mm": schedule.threshold_mm,
            "summary": schedule.summary,
        }
