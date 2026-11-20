"""Read-only Rachio forecast calendar, sharing the Supervisor evidence cache."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import RachioSupervisorEntity
from .reporting import run_datetime


def calendar_event(run: dict[str, object]) -> CalendarEvent:
    """Keep soak completion separate from actual watering duration."""
    if run["skipped"]:
        summary = f"Predicted skip: {run['schedule_name']}"
        detail = (
            f"Predicted skip cause: {run['skip_cause']}. No watering duration reported."
        )
    else:
        summary = str(run["schedule_name"])
        seconds = run["watering_seconds"]
        detail = (
            f"Watering: {seconds / 60:g} minutes. " if seconds is not None else ""
        ) + f"Elapsed window: {run['elapsed_seconds'] / 60:g} minutes."
        if run["cycle_soak"]:
            detail += " Cycle and soak; end time includes soak time."
        for zone in run["zones"]:
            detail += (
                f"\n{zone['zone_name']}: {zone['duration_seconds'] / 60:g} minutes."
            )
    return CalendarEvent(
        start=run_datetime(run["start"]),
        end=run_datetime(run["end"]),
        summary=summary,
        description=detail
        + "\nRachio prediction for the next 14 days; may change with weather.",
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add one calendar per Supervisor site without extra API polling."""
    async_add_entities([RachioUpcomingRunsCalendar(hass.data[DOMAIN][entry.entry_id])])


class RachioUpcomingRunsCalendar(RachioSupervisorEntity, CalendarEntity):
    """Expose predicted runs and skips using native HA calendar cards."""

    _attr_name = "Upcoming runs"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_upcoming_runs"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data.upcoming_runs_status == "available"
        )

    @property
    def event(self) -> CalendarEvent | None:
        if not self.available:
            return None
        now = dt_util.now()
        # Predicted skips appear in calendar history/window queries but are not
        # the next watering event or an indication that watering is active.
        return next(
            (
                calendar_event(run)
                for run in self.coordinator.data.upcoming_runs
                if not run["skipped"] and run_datetime(run["end"]) > now
            ),
            None,
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        if not self.available:
            raise HomeAssistantError(
                "Rachio upcoming runs are unavailable; retry after refresh."
            )
        return [
            calendar_event(run)
            for run in self.coordinator.data.upcoming_runs
            if run_datetime(run["start"]) < end_date
            and run_datetime(run["end"]) > start_date
        ]

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "source": "rachio_upcoming_runs",
            "forecast_days": 14,
            "status": self.coordinator.data.upcoming_runs_status,
            "last_success_at": self.coordinator.data.upcoming_runs_updated_at,
            "includes_predicted_skips": True,
        }
