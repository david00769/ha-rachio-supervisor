"""Coordinator scaffold for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
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

TZ = ZoneInfo("UTC")


@dataclass(slots=True)
class SupervisorSnapshot:
    """Minimal public snapshot for the scaffold stage."""

    health: str
    mode: str
    action_posture: str
    site_name: str
    rachio_config_entry_id: str
    rain_actuals_entity: str
    zone_count: int
    last_refresh: str


class RachioSupervisorCoordinator(DataUpdateCoordinator[SupervisorSnapshot]):
    """Scaffold coordinator for the public seed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
        )
        self.entry = entry

    async def _async_update_data(self) -> SupervisorSnapshot:
        """Return a scaffold snapshot.

        The first public seed intentionally exposes a lightweight runtime shape
        only. The real Rachio webhook/event/moisture supervisor logic will be
        implemented on top of this contract.
        """
        data = {**self.entry.data, **self.entry.options}
        observe_first = data.get(CONF_OBSERVE_FIRST, True)
        mode = "observe_only" if observe_first else "manual_review"
        moisture_mode = data.get(CONF_ALLOW_MOISTURE_WRITE_BACK, False)
        action_posture = (
            "per_zone_opt_in_with_write_back_available"
            if moisture_mode
            else "per_zone_opt_in"
        )
        return SupervisorSnapshot(
            health="scaffold",
            mode=mode,
            action_posture=action_posture,
            site_name=data.get(CONF_SITE_NAME, self.entry.title),
            rachio_config_entry_id=data.get(CONF_RACHIO_CONFIG_ENTRY_ID, ""),
            rain_actuals_entity=data.get(CONF_RAIN_ACTUALS_ENTITY, ""),
            zone_count=int(data.get(CONF_ZONE_COUNT, 0)),
            last_refresh=datetime.now(tz=TZ).isoformat(),
        )

