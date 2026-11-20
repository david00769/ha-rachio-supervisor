"""Offline contract checks against an installed Home Assistant (no import stubs).

Run separately from test_supervisor_logic, whose narrow import stubs are deliberate.
Requires Home Assistant 2026.10.4 and Python 3.14. No API calls or watering occur.
"""

import logging
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.rachio_supervisor.calendar import (
    RachioUpcomingRunsCalendar,
    async_setup_entry,
    calendar_event,
)
from custom_components.rachio_supervisor.const import DOMAIN
from custom_components.rachio_supervisor.reporting import normalize_upcoming_runs


class RealHomeAssistantCalendarTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.temp.name)
        device_registry.async_setup(self.hass)
        await device_registry.async_load(self.hass, load_empty=True)
        await entity_registry.async_load(self.hass, load_empty=True)
        self.entry = SimpleNamespace(entry_id="synthetic-entry", title="Synthetic Site")
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            logging.getLogger(__name__),
            name="test-rachio-reporting",
            config_entry=None,
            update_interval=timedelta(minutes=5),
        )
        self.coordinator.entry = self.entry
        self.runs = normalize_upcoming_runs(
            [
                {
                    "startTime": "2026-11-08T05:17:00-08:00",
                    "endTime": "2026-11-08T06:03:00-08:00",
                    "scheduleRuleId": "synthetic-rule",
                    "scheduleName": "Synthetic Lawn",
                    "skipped": False,
                    "cycleSoak": True,
                    "totalDuration": 960,
                    "zones": [
                        {
                            "zoneId": "synthetic-zone",
                            "zoneNumber": 1,
                            "zoneName": "Synthetic Zone",
                            "duration": 960,
                        }
                    ],
                }
            ]
        )
        self.coordinator.async_set_updated_data(
            SimpleNamespace(
                upcoming_runs=self.runs,
                upcoming_runs_status="available",
                upcoming_runs_updated_at="2026-11-01T12:00:00+00:00",
            )
        )
        self.hass.data[DOMAIN] = {self.entry.entry_id: self.coordinator}

    async def asyncTearDown(self):
        await self.hass.async_stop()
        self.temp.cleanup()

    async def test_actual_calendar_platform_add_state_refresh_and_remove(self):
        entities = []
        await async_setup_entry(self.hass, self.entry, entities.extend)
        self.assertEqual(len(entities), 1)
        self.assertIsInstance(entities[0], CalendarEntity)
        # The standalone test platform has no config entry/device association;
        # device metadata is covered by the integration base entity tests.
        entities[0]._attr_device_info = None
        component = EntityComponent(logging.getLogger(__name__), "calendar", self.hass)
        with patch(
            "homeassistant.util.dt.now",
            return_value=datetime(2026, 11, 1, tzinfo=UTC),
        ):
            await component.async_add_entities(entities)
            await self.hass.async_block_till_done()
            entity = entities[0]
            state = self.hass.states.get(entity.entity_id)
            self.assertIsNotNone(state)
            self.assertEqual(state.state, "off")
            self.assertEqual(state.attributes["message"], "Synthetic Lawn")
            self.assertEqual(state.attributes["forecast_days"], 14)
            self.assertFalse(entity.supported_features)
            self.coordinator.async_set_updated_data(
                SimpleNamespace(
                    upcoming_runs=(),
                    upcoming_runs_status="unavailable",
                    upcoming_runs_updated_at=None,
                )
            )
            await self.hass.async_block_till_done()
            self.assertEqual(
                self.hass.states.get(entity.entity_id).state, "unavailable"
            )
            await component.async_remove_entity(entity.entity_id)
            await self.hass.async_block_till_done()
            self.assertTrue(
                self.hass.states.get(entity.entity_id).attributes.get("restored")
            )
            self.assertFalse(self.coordinator._listeners)

    async def test_real_calendar_event_serialization_and_range(self):
        event = calendar_event(self.runs[0])
        self.assertIsInstance(event, CalendarEvent)
        self.assertEqual(event.as_dict()["start"], self.runs[0]["start"])
        self.assertIn("16 minutes", event.description)
        self.assertIn("46 minutes", event.description)
        entity = RachioUpcomingRunsCalendar(self.coordinator)
        events = await entity.async_get_events(
            self.hass,
            datetime(2026, 11, 8, 13, 30, tzinfo=UTC),
            datetime(2026, 11, 8, 14, 0, tzinfo=UTC),
        )
        self.assertEqual(
            len(events), 1
        )  # Includes an event overlapping the requested window.

    async def test_real_calendar_accepts_skip_without_watering_fields(self):
        raw = {
            "startTime": "2026-11-07T05:17:00-08:00",
            "endTime": "2026-11-07T06:03:00-08:00",
            "scheduleRuleId": "synthetic-rule",
            "scheduleName": "Synthetic Lawn",
            "skipped": True,
            "skipCause": "FREEZE",
            "zones": [],
        }
        run = normalize_upcoming_runs([raw])[0]
        event = calendar_event(run)
        self.assertTrue(event.summary.startswith("Predicted skip:"))
        self.assertIn("FREEZE", event.description)
        self.assertIn("No watering duration reported", event.description)


if __name__ == "__main__":
    unittest.main()
