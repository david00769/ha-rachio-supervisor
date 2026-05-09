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
    async_add_entities(
        RachioSupervisorSensor(coordinator, description) for description in DESCRIPTIONS
    )


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

