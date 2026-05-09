"""Deterministic logic tests for the public Rachio Supervisor seed.

These tests run without a full Home Assistant install by stubbing the narrow
surface the current coordinator and service helpers import.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import patch


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

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            return None

        async def async_set_unique_id(self, unique_id: str) -> None:
            self._last_unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            return None

        def async_show_form(self, *, step_id: str, data_schema=None, description_placeholders=None):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "description_placeholders": description_placeholders,
            }

        def async_create_entry(self, *, title: str, data: dict):
            return {"type": "create_entry", "title": title, "data": data}

        def async_abort(self, *, reason: str):
            return {"type": "abort", "reason": reason}

    class OptionsFlow:
        @property
        def config_entry(self):
            return getattr(self, "_config_entry", None)

        def async_abort(self, *, reason: str):
            return {"type": "abort", "reason": reason}

        def async_show_form(self, *, step_id: str, data_schema=None, description_placeholders=None):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "description_placeholders": description_placeholders,
            }

        def async_create_entry(self, *, title: str, data: dict):
            return {"type": "create_entry", "title": title, "data": data}

    config_entries.ConfigEntry = ConfigEntry
    config_entries.ConfigEntryState = ConfigEntryState
    config_entries.ConfigFlow = ConfigFlow
    config_entries.OptionsFlow = OptionsFlow
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

    selector = types.ModuleType("homeassistant.helpers.selector")

    class _SelectorConfig:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    class _Selector:
        def __init__(self, config) -> None:
            self.config = config

    class TextSelectorType:
        TEXT = "text"

    class SelectSelectorMode:
        DROPDOWN = "dropdown"

    class NumberSelectorMode:
        BOX = "box"

    class TextSelectorConfig(_SelectorConfig):
        pass

    class SelectSelectorConfig(_SelectorConfig):
        pass

    class NumberSelectorConfig(_SelectorConfig):
        pass

    class EntitySelectorConfig(_SelectorConfig):
        pass

    class TextSelector(_Selector):
        pass

    class SelectSelector(_Selector):
        pass

    class NumberSelector(_Selector):
        pass

    class BooleanSelector(_Selector):
        def __init__(self) -> None:
            self.config = None

    class EntitySelector(_Selector):
        pass

    @dataclass
    class SelectOptionDict:
        value: str
        label: str

    selector.TextSelectorType = TextSelectorType
    selector.SelectSelectorMode = SelectSelectorMode
    selector.NumberSelectorMode = NumberSelectorMode
    selector.TextSelectorConfig = TextSelectorConfig
    selector.SelectSelectorConfig = SelectSelectorConfig
    selector.NumberSelectorConfig = NumberSelectorConfig
    selector.EntitySelectorConfig = EntitySelectorConfig
    selector.TextSelector = TextSelector
    selector.SelectSelector = SelectSelector
    selector.NumberSelector = NumberSelector
    selector.BooleanSelector = BooleanSelector
    selector.EntitySelector = EntitySelector
    selector.SelectOptionDict = SelectOptionDict
    sys.modules["homeassistant.helpers.selector"] = selector
    helpers_pkg.selector = selector

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

    device_registry = types.ModuleType("homeassistant.helpers.device_registry")

    @dataclass
    class DeviceInfo:
        identifiers: set[tuple[str, str]]
        manufacturer: str
        model: str
        name: str

    device_registry.DeviceInfo = DeviceInfo
    sys.modules["homeassistant.helpers.device_registry"] = device_registry

    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")

    class AddEntitiesCallback:
        pass

    entity_platform.AddEntitiesCallback = AddEntitiesCallback
    sys.modules["homeassistant.helpers.entity_platform"] = entity_platform

    update = types.ModuleType("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __class_getitem__(cls, _item):
            return cls

        async def async_request_refresh(self) -> None:
            return None

    class CoordinatorEntity:
        def __init__(self, coordinator) -> None:
            self.coordinator = coordinator

        def __class_getitem__(cls, _item):
            return cls

    update.DataUpdateCoordinator = DataUpdateCoordinator
    update.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = update

    util_pkg = types.ModuleType("homeassistant.util")
    sys.modules["homeassistant.util"] = util_pkg

    dt_mod = types.ModuleType("homeassistant.util.dt")
    dt_mod.as_local = lambda value: value
    dt_mod.now = lambda: datetime(2026, 5, 9, 12, 0, 0)
    sys.modules["homeassistant.util.dt"] = dt_mod

    util_pkg.slugify = lambda value: str(value).strip().lower().replace(" ", "_")

    sensor_component = types.ModuleType("homeassistant.components.sensor")

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription:
        key: str
        translation_key: str | None = None
        entity_category: object | None = None

    class SensorEntity:
        pass

    sensor_component.SensorEntity = SensorEntity
    sensor_component.SensorEntityDescription = SensorEntityDescription
    sys.modules["homeassistant.components.sensor"] = sensor_component

    entity_category = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
    const.EntityCategory = entity_category

    voluptuous = types.ModuleType("voluptuous")

    class _Schema:
        def __init__(self, value):
            self.value = value

        def __call__(self, payload):
            return payload

    def Schema(value):
        return _Schema(value)

    def _freeze_marker_value(value):
        if isinstance(value, list):
            return tuple(_freeze_marker_value(item) for item in value)
        if isinstance(value, dict):
            return tuple(sorted((key, _freeze_marker_value(item)) for key, item in value.items()))
        return value

    @dataclass(frozen=True)
    class _VolMarker:
        kind: str
        value: object
        default: object = None

        def __hash__(self) -> int:
            return hash(
                (
                    self.kind,
                    _freeze_marker_value(self.value),
                    _freeze_marker_value(self.default),
                )
            )

    def Optional(value, default=None):
        return _VolMarker("optional", value, default)

    def Required(value, default=None):
        return _VolMarker("required", value, default)

    voluptuous.Schema = Schema
    voluptuous.Optional = Optional
    voluptuous.Required = Required
    sys.modules["voluptuous"] = voluptuous


_install_homeassistant_stubs()

integration_init = importlib.import_module("custom_components.rachio_supervisor")
config_flow = importlib.import_module("custom_components.rachio_supervisor.config_flow")
diagnostics = importlib.import_module("custom_components.rachio_supervisor.diagnostics")
sensor_module = importlib.import_module("custom_components.rachio_supervisor.sensor")
from custom_components.rachio_supervisor.const import DOMAIN
from custom_components.rachio_supervisor.coordinator import (
    FlowAlertSnapshot,
    RachioEvidenceSnapshot,
    RachioSupervisorCoordinator,
    ScheduleSnapshot,
    SupervisorSnapshot,
    build_flow_alert_snapshots,
    build_moisture_review_items,
    evaluate_cached_evidence_health,
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


class RuntimeHealthAndMoistureTests(unittest.TestCase):
    def test_fresh_cached_evidence_is_healthy_without_optional_inputs(self) -> None:
        evidence = RachioEvidenceSnapshot(
            controller_name="Yard Controller",
            controller_id="controller-1",
            last_event_summary="Pots - Dawn Micro ran for 3 minutes.",
            last_event_at="2026-05-10T06:52:35+10:00",
            last_run_summary="Pots - Dawn Micro ran for 3 minutes.",
            last_run_at="2026-05-10T06:52:35+10:00",
            last_skip_summary="none",
            last_skip_at=None,
            observed_rain_24h="unknown",
            observed_rain_status="not_reported",
            observed_rain_best_event=None,
            webhook_count=1,
            webhook_health="registered",
            webhook_url="https://example.invalid/webhook",
            webhook_external_id="abc",
            flow_alert_snapshots=(),
            schedule_snapshots=(),
        )

        health, reason, webhook_health = evaluate_cached_evidence_health(
            evidence=evidence,
            current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
        )

        self.assertEqual(health, "healthy")
        self.assertEqual(webhook_health, "healthy")
        self.assertIn("event history is fresh", reason)

    def test_stale_cached_evidence_is_degraded(self) -> None:
        evidence = RachioEvidenceSnapshot(
            controller_name="Yard Controller",
            controller_id="controller-1",
            last_event_summary="Old event",
            last_event_at="2026-05-08T00:00:00+10:00",
            last_run_summary="Old run",
            last_run_at="2026-05-08T00:00:00+10:00",
            last_skip_summary="none",
            last_skip_at=None,
            observed_rain_24h="unknown",
            observed_rain_status="not_reported",
            observed_rain_best_event=None,
            webhook_count=1,
            webhook_health="registered",
            webhook_url="https://example.invalid/webhook",
            webhook_external_id="abc",
            flow_alert_snapshots=(),
            schedule_snapshots=(),
        )

        health, reason, webhook_health = evaluate_cached_evidence_health(
            evidence=evidence,
            current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
        )

        self.assertEqual(health, "degraded")
        self.assertEqual(webhook_health, "stale")
        self.assertIn("older than", reason)

    def test_moisture_review_items_exist_even_without_recommendations(self) -> None:
        schedule = ScheduleSnapshot(
            rule_id="rule-1",
            name="Rear Protea Shade Bed",
            status="idle",
            reason="none",
            catch_up_candidate="not_needed",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id="switch.schedule_protea",
            zone_entity_id="switch.zone_protea",
            controller_zone_id="zone-1",
            moisture_entity_id="sensor.rear_protea_moisture",
            moisture_value="58",
            moisture_band="wet",
            moisture_status="ok",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="none",
            runtime_minutes=3,
            last_run_at="2026-05-09T11:00:00",
            last_skip_at="2026-05-09T10:00:00",
            summary="Rear Protea review summary",
            threshold_mm=6.35,
            observed_mm=None,
        )

        items = build_moisture_review_items((schedule,))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["schedule_name"], "Rear Protea Shade Bed")
        self.assertEqual(items[0]["moisture_band"], "wet")
        self.assertEqual(items[0]["recommended_action"], "none")


class ConfigFlowBehaviorTests(unittest.TestCase):
    def _hass(self) -> SimpleNamespace:
        return SimpleNamespace(
            states=SimpleNamespace(get=lambda _entity_id: None),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )

    def test_user_step_aborts_without_linked_rachio_entries(self) -> None:
        flow = config_flow.RachioSupervisorConfigFlow()
        flow.hass = self._hass()

        with patch.object(config_flow, "rachio_entry_options", return_value=[]):
            result = asyncio.run(flow.async_step_user())

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "no_rachio_entries")

    def test_user_step_shows_form_when_entries_exist(self) -> None:
        flow = config_flow.RachioSupervisorConfigFlow()
        flow.hass = self._hass()

        with patch.object(
            config_flow,
            "rachio_entry_options",
            return_value=[("entry-1", "Sugarloaf Rachio")],
        ):
            result = asyncio.run(flow.async_step_user())

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")

    def test_config_flow_skips_moisture_map_when_no_sensors_selected(self) -> None:
        flow = config_flow.RachioSupervisorConfigFlow()
        flow.hass = self._hass()
        flow._basic_input = {
            "site_name": "Sugarloaf",
            "rachio_config_entry_id": "entry-1",
            "moisture_sensor_entities": [],
        }
        flow._policy_input = {
            "auto_catch_up_schedule_entities": [],
            "auto_missed_run_schedule_entities": [],
        }

        result = asyncio.run(flow.async_step_moisture_map())

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Sugarloaf")
        self.assertEqual(result["data"]["schedule_moisture_map"], {})
        self.assertEqual(flow._last_unique_id, "rachio_supervisor::entry-1")

    def test_config_flow_collects_explicit_moisture_mapping(self) -> None:
        state_map = {
            "sensor.moisture_pots": SimpleNamespace(
                attributes={"friendly_name": "Pots moisture"}
            )
        }
        flow = config_flow.RachioSupervisorConfigFlow()
        flow.hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id)),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )
        flow._basic_input = {
            "site_name": "Sugarloaf",
            "rachio_config_entry_id": "entry-1",
            "moisture_sensor_entities": ["sensor.moisture_pots"],
        }
        flow._policy_input = {
            "auto_catch_up_schedule_entities": [],
            "auto_missed_run_schedule_entities": [],
        }
        flow._schedule_options = [("switch.schedule_pots", "Pots - Dawn Micro")]

        prompt = asyncio.run(flow.async_step_moisture_map())
        self.assertEqual(prompt["type"], "form")
        self.assertEqual(prompt["step_id"], "moisture_map")

        result = asyncio.run(
            flow.async_step_moisture_map({"moisture_entity": "sensor.moisture_pots"})
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"]["schedule_moisture_map"],
            {"switch.schedule_pots": "sensor.moisture_pots"},
        )

    def test_options_flow_skips_mapping_when_no_sensors_selected(self) -> None:
        entry = SimpleNamespace(data={"site_name": "Sugarloaf"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()
        flow._basic_input = {"moisture_sensor_entities": []}
        flow._policy_input = {"auto_catch_up_schedule_entities": []}

        result = asyncio.run(flow.async_step_moisture_map())

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["schedule_moisture_map"], {})

    def test_options_flow_uses_private_entry_storage(self) -> None:
        entry = SimpleNamespace(data={"site_name": "Sugarloaf"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)

        self.assertIs(flow._entry, entry)
        self.assertIsNone(flow.config_entry)

    def test_options_flow_aborts_without_linked_rachio_entries(self) -> None:
        entry = SimpleNamespace(data={"site_name": "Sugarloaf"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()

        with patch.object(config_flow, "rachio_entry_options", return_value=[]):
            result = asyncio.run(flow.async_step_init())

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "no_rachio_entries")

    def test_options_flow_recovers_when_saved_linked_entry_is_missing(self) -> None:
        entry = SimpleNamespace(
            data={"site_name": "Sugarloaf", "rachio_config_entry_id": "missing-entry"},
            options={},
        )
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()

        with patch.object(
            config_flow,
            "rachio_entry_options",
            return_value=[("entry-1", "Sugarloaf Rachio")],
        ):
            result = asyncio.run(flow.async_step_init())

        self.assertEqual(result["type"], "form")
        schema_markers = list(result["data_schema"].value.keys())
        linked_marker = next(
            marker
            for marker in schema_markers
            if getattr(marker, "value", None) == "rachio_config_entry_id"
        )
        self.assertEqual(linked_marker.default, "entry-1")


class DiagnosticsAndEntityTests(unittest.TestCase):
    def _snapshot(self) -> SupervisorSnapshot:
        schedule = ScheduleSnapshot(
            rule_id="rule-1",
            name="Pots - Dawn Micro",
            status="idle",
            reason="none",
            catch_up_candidate="not_needed",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id="switch.schedule_pots",
            zone_entity_id="switch.zone_pots",
            controller_zone_id="zone-1",
            moisture_entity_id="sensor.pots_moisture",
            moisture_value="42",
            moisture_band="target",
            moisture_status="ok",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="none",
            runtime_minutes=3,
            last_run_at="2026-05-09T11:00:00",
            last_skip_at="2026-05-09T10:00:00",
            summary="Pots review summary",
            threshold_mm=6.35,
            observed_mm=None,
        )
        return SupervisorSnapshot(
            health="healthy",
            supervisor_mode="healthy",
            supervisor_reason="Fresh evidence.",
            data_completeness="warnings",
            missing_inputs=("rain_actuals_unconfigured",),
            runtime_integrity="healthy",
            mode="observe_only",
            action_posture="per_zone_opt_in",
            site_name="Sugarloaf",
            linked_entry_title="Sugarloaf Rachio",
            linked_entry_state="loaded",
            rachio_config_entry_id="entry-1",
            rain_actuals_entity="sensor.rain_24h",
            zone_count=7,
            configured_zone_count=7,
            active_zone_count=0,
            active_schedule_count=0,
            connectivity="on",
            rain_state="off",
            rain_delay_state="off",
            standby_state="off",
            actual_rain_value="0.0",
            actual_rain_unit="mm",
            rain_actuals_status="ok",
            controller_name="Yard Controller",
            controller_id="controller-1",
            last_event_summary="Last event",
            last_event_at="2026-05-09T12:00:00",
            last_run_summary="Last run",
            last_run_at="2026-05-09T11:00:00",
            last_skip_summary="Last skip",
            last_skip_at="2026-05-09T10:00:00",
            observed_rain_24h="unknown",
            observed_rain_status="not_reported",
            observed_rain_best_event={"latest_skip_event_id": "skip-1"},
            webhook_count=1,
            webhook_health="healthy",
            webhook_url="https://example.invalid/webhook",
            webhook_external_id="homeassistant.rachio:abc",
            ready_moisture_write_count=1,
            moisture_write_queue="Pots - Dawn Micro",
            recommended_moisture_write_count=1,
            recommended_moisture_write_queue="Pots - Dawn Micro",
            active_recommendation_count=1,
            active_recommendation_queue="Pots - Dawn Micro",
            acknowledged_recommendation_count=0,
            acknowledged_recommendation_queue="none",
            catch_up_evidence_status="monitoring",
            catch_up_evidence_reason="monitoring",
            catch_up_schedule_name=None,
            catch_up_runtime_minutes=0,
            catch_up_summary="No active catch-up candidate.",
            catch_up_decision_at=None,
            last_catch_up_decision="none",
            active_flow_alert_count=0,
            flow_alert_queue="none",
            last_flow_alert_decision="none",
            last_reconciliation="2026-05-09T12:15:00",
            last_moisture_write_status="none",
            last_moisture_write_at=None,
            last_moisture_write_schedule=None,
            last_moisture_write_value=None,
            last_refresh="2026-05-09T12:15:00",
            notes=("All good",),
            moisture_review_items=(
                {
                    "schedule_name": "Pots - Dawn Micro",
                    "mapped_sensor": "sensor.pots_moisture",
                    "moisture_band": "target",
                    "posture_note": "Moisture watch",
                    "recommended_action": "none",
                    "review_state": "none",
                    "moisture_write_back_ready": "ready",
                    "moisture_value": "42",
                },
            ),
            discovered_entities={"entity_count": 10},
            schedule_snapshots=(schedule,),
        )

    def test_diagnostics_payload_contains_snapshot_and_notes(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(data=snapshot)
        hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        entry = SimpleNamespace(
            entry_id="entry-1",
            title="Sugarloaf",
            data={"site_name": "Sugarloaf"},
            options={"observe_first": True},
        )

        payload = asyncio.run(diagnostics.async_get_config_entry_diagnostics(hass, entry))

        self.assertEqual(payload["domain"], DOMAIN)
        self.assertEqual(payload["snapshot"]["health"], "healthy")
        self.assertIn("Automatic irrigation behavior remains intentionally narrow and opt-in.", payload["notes"])

    def test_site_sensor_sets_explicit_name_and_attributes(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Sugarloaf"),
            data=snapshot,
            _cached_evidence=None,
        )
        description = next(
            item for item in sensor_module.DESCRIPTIONS if item.key == "recommended_moisture_write_count"
        )

        entity = sensor_module.RachioSupervisorSensor(coordinator, description)

        self.assertEqual(entity._attr_name, "Recommended moisture writes")
        self.assertEqual(entity.native_value, "1")
        self.assertEqual(
            entity.extra_state_attributes["recommended_moisture_write_queue"],
            "Pots - Dawn Micro",
        )
        self.assertEqual(
            entity.extra_state_attributes["moisture_review_items"][0]["schedule_name"],
            "Pots - Dawn Micro",
        )

    def test_health_sensor_exposes_runtime_and_data_completeness(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Sugarloaf"),
            data=snapshot,
            _cached_evidence=None,
        )
        description = next(
            item for item in sensor_module.DESCRIPTIONS if item.key == "health"
        )

        entity = sensor_module.RachioSupervisorSensor(coordinator, description)

        self.assertEqual(entity.native_value, "healthy")
        self.assertEqual(entity.extra_state_attributes["runtime_integrity"], "healthy")
        self.assertEqual(entity.extra_state_attributes["data_completeness"], "warnings")
        self.assertEqual(
            entity.extra_state_attributes["missing_inputs"],
            ["rain_actuals_unconfigured"],
        )

    def test_last_run_sensor_exposes_compact_decision_fields(self) -> None:
        snapshot = self._snapshot()
        snapshot = replace(
            snapshot,
            last_run_summary="Pots - Dawn Micro ran for 3 minutes.",
        )
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Sugarloaf"),
            data=snapshot,
            _cached_evidence=None,
        )
        description = next(
            item for item in sensor_module.DESCRIPTIONS if item.key == "last_run_event"
        )

        entity = sensor_module.RachioSupervisorSensor(coordinator, description)

        self.assertEqual(entity.extra_state_attributes["subject"], "Pots - Dawn Micro")
        self.assertEqual(entity.extra_state_attributes["brief"], "ran 3 min")
        self.assertEqual(entity.extra_state_attributes["at_local"], "11:00")

    def test_schedule_sensor_exposes_schedule_context(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Sugarloaf"),
            data=snapshot,
        )
        schedule = snapshot.schedule_snapshots[0]

        entity = sensor_module.RachioSupervisorScheduleSensor(
            coordinator,
            schedule,
            "moisture_band",
            "Moisture",
        )

        self.assertEqual(entity.native_value, "target")
        self.assertEqual(entity.extra_state_attributes["moisture_entity_id"], "sensor.pots_moisture")
        self.assertEqual(entity.extra_state_attributes["controller_zone_id"], "zone-1")


if __name__ == "__main__":
    unittest.main()
