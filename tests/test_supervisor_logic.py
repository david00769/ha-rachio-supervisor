"""Deterministic logic tests for the public Rachio Supervisor seed.

These tests run without a full Home Assistant install by stubbing the narrow
surface the current coordinator and service helpers import.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
from pathlib import Path
import sys
import types
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _install_homeassistant_stubs() -> None:
    """Install minimal import-time stubs for Home Assistant modules."""

    if "homeassistant" in sys.modules:
        return

    homeassistant = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = homeassistant

    config_entries = types.ModuleType("homeassistant.config_entries")

    class _ConfigEntryStateValue:
        def __init__(self, value: str) -> None:
            self.value = value

        def __repr__(self) -> str:
            return f"ConfigEntryState({self.value!r})"

    class ConfigEntryState:
        LOADED = _ConfigEntryStateValue("loaded")
        NOT_LOADED = _ConfigEntryStateValue("not_loaded")
        SETUP_IN_PROGRESS = _ConfigEntryStateValue("setup_in_progress")

    class ConfigEntry:
        def __init__(
            self,
            *,
            entry_id: str = "entry-1",
            title: str = "Rachio",
            data: dict | None = None,
            options: dict | None = None,
            state: object | None = None,
        ) -> None:
            self.entry_id = entry_id
            self.title = title
            self.data = data or {}
            self.options = options or {}
            self.state = state or ConfigEntryState.LOADED

    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigEntryState = ConfigEntryState
    sys.modules["homeassistant.config_entries"] = config_entries

    const = types.ModuleType("homeassistant.const")
    const.CONF_API_KEY = "api_key"
    const.STATE_UNAVAILABLE = "unavailable"
    const.STATE_UNKNOWN = "unknown"

    class Platform:
        SENSOR = "sensor"

    const.Platform = Platform
    sys.modules["homeassistant.const"] = const

    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    class ServiceCall:
        def __init__(self, data: dict | None = None) -> None:
            self.data = data or {}

    def callback(func):
        return func

    core.HomeAssistant = HomeAssistant
    core.ServiceCall = ServiceCall
    core.callback = callback
    sys.modules["homeassistant.core"] = core

    exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    exceptions.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant.exceptions"] = exceptions

    helpers_pkg = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers_pkg

    cv = types.ModuleType("homeassistant.helpers.config_validation")
    cv.entity_ids = object()
    cv.entity_id = object()
    cv.string = object()
    sys.modules["homeassistant.helpers.config_validation"] = cv

    er = types.ModuleType("homeassistant.helpers.entity_registry")

    class RegistryEntry:
        pass

    def async_get(_hass):
        return types.SimpleNamespace(entities={})

    er.RegistryEntry = RegistryEntry
    er.async_get = async_get
    sys.modules["homeassistant.helpers.entity_registry"] = er

    update = types.ModuleType("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __class_getitem__(cls, _item):
            return cls

        async def async_request_refresh(self) -> None:
            return None

    update.DataUpdateCoordinator = DataUpdateCoordinator
    sys.modules["homeassistant.helpers.update_coordinator"] = update

    util_pkg = types.ModuleType("homeassistant.util")
    sys.modules["homeassistant.util"] = util_pkg

    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.as_local = lambda value: value
    dt_mod.now = lambda: datetime(2026, 5, 9, 12, 0, 0)
    sys.modules["homeassistant.util.dt"] = dt_mod

    voluptuous = types.ModuleType("voluptuous")

    class _Schema:
        def __init__(self, value):
            self.value = value

        def __call__(self, payload):
            return payload

    def Schema(value):
        return _Schema(value)

    def Optional(value):
        return value

    voluptuous.Schema = Schema
    voluptuous.Optional = Optional
    sys.modules["voluptuous"] = voluptuous


_install_homeassistant_stubs()

integration_init = importlib.import_module("custom_components.rachio_supervisor")
from custom_components.rachio_supervisor.const import DOMAIN
from custom_components.rachio_supervisor.coordinator import (
    FlowAlertSnapshot,
    RachioSupervisorCoordinator,
    build_flow_alert_snapshots,
    observed_rain_24h,
)


def _event(
    event_date_ms: int,
    *,
    event_type: str,
    sub_type: str,
    summary: str,
    event_id: str,
) -> dict[str, object]:
    return {
        "id": event_id,
        "eventDate": event_date_ms,
        "type": event_type,
        "subType": sub_type,
        "summary": summary,
    }


class FlowAlertLifecycleTests(unittest.TestCase):
    def test_low_flow_without_later_calibration_requires_calibration(self) -> None:
        controller = {
            "zones": [{"id": "zone-1", "name": "Front Lawn", "enabled": True}],
        }
        events = [
            _event(
                1_714_953_600_000,
                event_type="ZONE_COMPLETED",
                sub_type="INFO",
                summary="Low flow in Front Lawn at runtime.",
                event_id="alert-1",
            )
        ]

        snapshots = build_flow_alert_snapshots(events, controller, set())

        self.assertEqual(len(snapshots), 1)
        snapshot = snapshots[0]
        self.assertEqual(snapshot.status, "calibration_required")
        self.assertEqual(snapshot.recommended_action, "run_native_calibration")
        self.assertEqual(snapshot.review_state, "pending_review")

    def test_later_calibration_without_prior_baseline_needs_review(self) -> None:
        controller = {
            "zones": [{"id": "zone-1", "name": "Front Lawn", "enabled": True}],
        }
        events = [
            _event(
                1_714_953_600_000,
                event_type="ZONE_COMPLETED",
                sub_type="INFO",
                summary="Low flow in Front Lawn at runtime.",
                event_id="alert-1",
            ),
            _event(
                1_714_954_200_000,
                event_type="SYSTEM",
                sub_type="INFO",
                summary="Baseline flow rate for Front Lawn is now set at 12.0 lpm.",
                event_id="baseline-1",
            ),
        ]

        snapshot = build_flow_alert_snapshots(events, controller, set())[0]

        self.assertEqual(snapshot.status, "calibrated_needs_review")
        self.assertEqual(snapshot.recommended_action, "review_baseline")
        self.assertEqual(snapshot.baseline_after_lpm, 12.0)
        self.assertIsNone(snapshot.baseline_before_lpm)

    def test_stable_post_alert_calibration_is_eligible_to_clear(self) -> None:
        controller = {
            "zones": [{"id": "zone-1", "name": "Front Lawn", "enabled": True}],
        }
        events = [
            _event(
                1_714_953_000_000,
                event_type="SYSTEM",
                sub_type="INFO",
                summary="Baseline flow rate for Front Lawn is now set at 10.0 lpm.",
                event_id="baseline-before",
            ),
            _event(
                1_714_953_600_000,
                event_type="ZONE_COMPLETED",
                sub_type="INFO",
                summary="Low flow in Front Lawn at runtime.",
                event_id="alert-1",
            ),
            _event(
                1_714_954_200_000,
                event_type="SYSTEM",
                sub_type="INFO",
                summary="Baseline flow rate for Front Lawn is now set at 10.8 lpm.",
                event_id="baseline-after",
            ),
        ]

        snapshot = build_flow_alert_snapshots(events, controller, set())[0]

        self.assertEqual(snapshot.status, "normal_after_calibration")
        self.assertEqual(snapshot.recommended_action, "clear_review")
        self.assertEqual(snapshot.review_state, "pending_review")
        self.assertAlmostEqual(snapshot.baseline_delta_percent or 0.0, 8.0)

    def test_material_post_alert_shift_suspects_problem(self) -> None:
        controller = {
            "zones": [{"id": "zone-1", "name": "Front Lawn", "enabled": True}],
        }
        events = [
            _event(
                1_714_953_000_000,
                event_type="SYSTEM",
                sub_type="INFO",
                summary="Baseline flow rate for Front Lawn is now set at 10.0 lpm.",
                event_id="baseline-before",
            ),
            _event(
                1_714_953_600_000,
                event_type="ZONE_COMPLETED",
                sub_type="INFO",
                summary="High flow in Front Lawn at runtime.",
                event_id="alert-1",
            ),
            _event(
                1_714_954_200_000,
                event_type="SYSTEM",
                sub_type="INFO",
                summary="Baseline flow rate for Front Lawn is now set at 13.0 lpm.",
                event_id="baseline-after",
            ),
        ]

        snapshot = build_flow_alert_snapshots(events, controller, set())[0]

        self.assertEqual(snapshot.status, "problem_suspected")
        self.assertEqual(snapshot.recommended_action, "inspect_zone")


class ObservedRainTests(unittest.TestCase):
    def test_skip_without_observed_mm_preserves_not_reported_state(self) -> None:
        current = datetime(2025, 5, 18, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            _event(
                1_747_526_400_000,
                event_type="WEATHER_INTELLIGENCE",
                sub_type="RAIN_SKIP",
                summary="Skipped watering due to rain event.",
                event_id="skip-1",
            )
        ]

        state, status, details = observed_rain_24h(events, current)

        self.assertEqual(state, "unknown")
        self.assertEqual(status, "not_reported")
        self.assertEqual(details["latest_skip_event_id"], "skip-1")


@dataclass
class _FakeSnapshot:
    rule_id: str
    status: str
    review_state: str = "pending_review"
    zone_name: str = "Front Lawn"
    alert_kind: str = "low_flow"
    alert_at: str = "2026-05-09T10:00:00"
    alert_summary: str = "Low flow in Front Lawn."
    reason: str = ""
    recommended_action: str = ""
    baseline_before_lpm: float | None = 10.0
    baseline_after_lpm: float | None = 10.2
    baseline_delta_percent: float | None = 2.0
    calibration_at: str | None = "2026-05-09T10:05:00"
    summary: str = "Front Lawn: low flow alert"


class FlowAlertClearTests(unittest.TestCase):
    def _coordinator_with_snapshots(
        self, *snapshots: FlowAlertSnapshot | _FakeSnapshot
    ) -> RachioSupervisorCoordinator:
        coordinator = object.__new__(RachioSupervisorCoordinator)
        coordinator._cached_evidence = types.SimpleNamespace(
            flow_alert_snapshots=tuple(snapshots)
        )
        coordinator._acknowledged_flow_alert_ids = set()
        coordinator._last_reconciliation = None
        coordinator._mode = "healthy"
        coordinator._degraded_since = None
        coordinator._healthy_reconciles = 0
        coordinator.entry = types.SimpleNamespace(data={}, options={})
        return coordinator

    def test_coordinator_rejects_non_eligible_clear(self) -> None:
        coordinator = self._coordinator_with_snapshots(
            _FakeSnapshot(rule_id="rule-1", status="problem_suspected")
        )

        with self.assertRaisesRegex(ValueError, "only be cleared"):
            coordinator.clear_flow_alert_review(rule_id="rule-1")

    def test_coordinator_clears_only_normal_after_calibration(self) -> None:
        coordinator = self._coordinator_with_snapshots(
            _FakeSnapshot(rule_id="rule-1", status="problem_suspected"),
            _FakeSnapshot(rule_id="rule-2", status="normal_after_calibration"),
        )

        coordinator.clear_flow_alert_review()

        self.assertEqual(coordinator._acknowledged_flow_alert_ids, {"rule-2"})

    def test_service_wrapper_rejects_non_eligible_status(self) -> None:
        coordinator = self._coordinator_with_snapshots(
            _FakeSnapshot(rule_id="rule-1", status="calibration_required")
        )
        refreshed: list[str] = []

        async def _refresh() -> None:
            refreshed.append("called")

        coordinator.async_request_refresh = _refresh
        coordinator.data = types.SimpleNamespace(site_name="Sugarloaf")
        hass = types.SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        call = types.SimpleNamespace(data={"site_name": "Sugarloaf", "rule_id": "rule-1"})

        with self.assertRaisesRegex(Exception, "only be cleared"):
            asyncio.run(
                integration_init._async_handle_clear_flow_alert_review(hass, call)
            )
        self.assertEqual(refreshed, [])

    def test_service_wrapper_clears_eligible_status(self) -> None:
        coordinator = self._coordinator_with_snapshots(
            _FakeSnapshot(rule_id="rule-1", status="normal_after_calibration")
        )
        refreshed: list[str] = []

        async def _refresh() -> None:
            refreshed.append("called")

        coordinator.async_request_refresh = _refresh
        coordinator.data = types.SimpleNamespace(site_name="Sugarloaf")
        hass = types.SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        call = types.SimpleNamespace(data={"site_name": "Sugarloaf", "rule_id": "rule-1"})

        asyncio.run(integration_init._async_handle_clear_flow_alert_review(hass, call))

        self.assertEqual(coordinator._acknowledged_flow_alert_ids, {"rule-1"})
        self.assertEqual(refreshed, ["called"])


class CadenceParityTests(unittest.TestCase):
    def _coordinator(self) -> RachioSupervisorCoordinator:
        coordinator = object.__new__(RachioSupervisorCoordinator)
        coordinator.entry = types.SimpleNamespace(data={}, options={})
        coordinator._mode = "healthy"
        coordinator._degraded_since = None
        coordinator._healthy_reconciles = 0
        coordinator._last_reconciliation = None
        return coordinator

    def test_degraded_fast_window_uses_fifteen_minute_cadence(self) -> None:
        coordinator = self._coordinator()
        coordinator._mode = "degraded"
        coordinator._degraded_since = "2026-05-09T09:00:00"
        coordinator._last_reconciliation = "2026-05-09T10:00:00"

        self.assertFalse(
            coordinator._should_reconcile(datetime.fromisoformat("2026-05-09T10:14:00"))
        )
        self.assertTrue(
            coordinator._should_reconcile(datetime.fromisoformat("2026-05-09T10:15:00"))
        )

    def test_healthy_mode_requires_daily_post_noon_reconcile(self) -> None:
        coordinator = self._coordinator()
        coordinator._last_reconciliation = "2026-05-08T12:30:00"

        self.assertFalse(
            coordinator._should_reconcile(datetime.fromisoformat("2026-05-09T12:14:00"))
        )
        self.assertTrue(
            coordinator._should_reconcile(datetime.fromisoformat("2026-05-09T12:15:00"))
        )

    def test_two_consecutive_healthy_reconciles_exit_degraded_mode(self) -> None:
        coordinator = self._coordinator()
        coordinator._mode = "degraded"
        coordinator._degraded_since = "2026-05-09T07:00:00"

        first = coordinator._apply_health_transition(
            "healthy", datetime.fromisoformat("2026-05-09T12:15:00")
        )
        second = coordinator._apply_health_transition(
            "healthy", datetime.fromisoformat("2026-05-09T13:15:00")
        )

        self.assertEqual(first, "degraded")
        self.assertEqual(second, "healthy")
        self.assertIsNone(coordinator._degraded_since)


if __name__ == "__main__":
    unittest.main()
