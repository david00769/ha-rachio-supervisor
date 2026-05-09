"""Base entity classes for Rachio Supervisor."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, TITLE
from .coordinator import RachioSupervisorCoordinator


class RachioSupervisorEntity(CoordinatorEntity[RachioSupervisorCoordinator]):
    """Base entity for the supervisor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RachioSupervisorCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            manufacturer="Community",
            model="Rachio Supervisor Scaffold",
            name=coordinator.entry.title or TITLE,
        )

