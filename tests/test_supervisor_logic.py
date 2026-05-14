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
import tempfile
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

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema=None,
            description_placeholders=None,
            errors=None,
        ):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "description_placeholders": description_placeholders,
                "errors": errors or {},
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

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema=None,
            description_placeholders=None,
            errors=None,
        ):
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "description_placeholders": description_placeholders,
                "errors": errors or {},
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
        PASSWORD = "password"

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

    def All(*validators):
        return validators

    def Coerce(value):
        return value

    def Range(**kwargs):
        return kwargs

    voluptuous.Schema = Schema
    voluptuous.Optional = Optional
    voluptuous.Required = Required
    voluptuous.All = All
    voluptuous.Coerce = Coerce
    voluptuous.Range = Range
    sys.modules["voluptuous"] = voluptuous


_install_homeassistant_stubs()

integration_init = importlib.import_module("custom_components.rachio_supervisor")
config_flow = importlib.import_module("custom_components.rachio_supervisor.config_flow")
coordinator_module = importlib.import_module("custom_components.rachio_supervisor.coordinator")
diagnostics = importlib.import_module("custom_components.rachio_supervisor.diagnostics")
photo_import = importlib.import_module("custom_components.rachio_supervisor.photo_import")
sensor_module = importlib.import_module("custom_components.rachio_supervisor.sensor")
from custom_components.rachio_supervisor.const import DOMAIN
from custom_components.rachio_supervisor.coordinator import (
    FlowAlertSnapshot,
    MoistureEvidenceCacheEntry,
    RachioEvidenceSnapshot,
    RachioSupervisorCoordinator,
    ScheduleSnapshot,
    SupervisorSnapshot,
    apply_moisture_mapping,
    build_rachio_evidence,
    build_rachio_weather_probe,
    build_rachio_weather_outlook,
    build_catch_up_action_label,
    build_catch_up_evidence_label,
    build_flow_alert_snapshots,
    build_moisture_review_items,
    build_zone_overview_items,
    discover_rain_source_candidates,
    evaluate_cached_evidence_health,
    evaluate_catch_up_decision,
    match_controller_zone_from_rule,
    match_zone_entity_by_controller_zone,
    observed_rain_24h,
    resolve_moisture_evidence,
    resolve_rain_actuals_entity,
    resolve_weather_underground_pws_actuals,
    schedule_rule_next_run,
    schedule_rule_watering_days,
)
from custom_components.rachio_supervisor.discovery import (
    LinkedRachioEntities,
    ScheduleEntityRef,
    ZoneEntityRef,
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


class _ImageResponse:
    def __init__(
        self,
        payload: bytes,
        *,
        content_type: str = "image/jpeg",
        content_length: int | None = None,
        include_content_length: bool = True,
    ) -> None:
        self._payload = payload
        self.headers = {
            "content-type": content_type,
        }
        if include_content_length:
            self.headers["content-length"] = str(
                content_length if content_length is not None else len(payload)
            )

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        return self._payload


class ZonePhotoImportTests(unittest.TestCase):
    def _linked_entities(self) -> LinkedRachioEntities:
        return LinkedRachioEntities(
            connectivity_entity_id=None,
            rain_entity_id=None,
            rain_delay_entity_id=None,
            standby_entity_id=None,
            zone_switches=("switch.zone_pots",),
            schedule_switches=("switch.schedule_pots",),
            zone_entities=(
                ZoneEntityRef("switch.zone_pots", "Pots Dawn Micro", "zone-1"),
            ),
            schedule_entities=(
                ScheduleEntityRef("switch.schedule_pots", "Pots - Dawn Micro", "rule-1"),
            ),
            all_entities=("switch.zone_pots", "switch.schedule_pots"),
        )

    def _client(self, *, image_url: str | None = "https://example.test/zone.jpg"):
        class _Client:
            def __init__(self) -> None:
                self.zone_calls = 0

            def list_person_devices(self):
                return [
                    {
                        "id": "device-1",
                        "name": "Test Controller",
                        "zones": [
                            {"id": "zone-1", "name": "Pots Dawn Micro", "enabled": True}
                        ],
                        "scheduleRules": [
                            {
                                "id": "rule-1",
                                "name": "Pots - Dawn Micro",
                                "enabled": True,
                                "totalDuration": 180,
                            }
                        ],
                    }
                ]

            def list_device_events(self, *_args, **_kwargs):
                return []

            def list_device_webhooks(self, _device_id):
                return []

            def get_zone(self, _zone_id):
                self.zone_calls += 1
                return {"id": "zone-1", "imageUrl": image_url} if image_url else {"id": "zone-1"}

        return _Client()

    def test_import_disabled_never_fetches_zone_detail(self) -> None:
        client = self._client()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = build_rachio_evidence(
                client,
                self._linked_entities(),
                1,
                True,
                "Test",
                None,
                None,
                set(),
                set(),
                set(),
                False,
                lambda *parts: str(root.joinpath(*parts)),
            )

        schedule = evidence.schedule_snapshots[0]
        self.assertEqual(client.zone_calls, 0)
        self.assertEqual(schedule.photo_import_status, "disabled")
        self.assertFalse(schedule.rachio_image_available)

    def test_zone_image_url_imports_to_cache(self) -> None:
        client = self._client()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(
                photo_import.urllib.request,
                "urlopen",
                return_value=_ImageResponse(b"\xff\xd8fake-jpeg\xff\xd9"),
            ):
                result = photo_import.import_rachio_zone_photo(
                    client=client,
                    zone_id="zone-1",
                    config_path=lambda *parts: str(root.joinpath(*parts)),
                    import_enabled=True,
                )
            path, url = photo_import.imported_zone_photo_paths(
                lambda *parts: str(root.joinpath(*parts)),
                "zone-1",
            )
            exists = path.exists()

        self.assertEqual(result.status, "imported")
        self.assertTrue(result.rachio_image_available)
        self.assertEqual(url, "/local/rachio-supervisor/imported-zones/zone-1.jpg")
        self.assertTrue(exists)

    def test_missing_image_url_uses_placeholder_metadata(self) -> None:
        client = self._client(image_url=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = photo_import.import_rachio_zone_photo(
                client=client,
                zone_id="zone-1",
                config_path=lambda *parts: str(root.joinpath(*parts)),
                import_enabled=True,
            )

        self.assertEqual(result.status, "missing")
        self.assertFalse(result.rachio_image_available)

    def test_enabled_evidence_import_never_reports_disabled_status(self) -> None:
        client = self._client(image_url=None)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            evidence = build_rachio_evidence(
                client,
                self._linked_entities(),
                1,
                True,
                "Test",
                None,
                None,
                set(),
                set(),
                set(),
                True,
                lambda *parts: str(root.joinpath(*parts)),
            )

        schedule = evidence.schedule_snapshots[0]
        self.assertEqual(client.zone_calls, 1)
        self.assertEqual(schedule.photo_import_status, "missing")
        self.assertEqual(schedule.photo_import_reason, "imageUrl_missing")

    def test_enabled_evidence_import_without_config_path_reports_missing(self) -> None:
        client = self._client()
        evidence = build_rachio_evidence(
            client,
            self._linked_entities(),
            1,
            True,
            "Test",
            None,
            None,
            set(),
            set(),
            set(),
            True,
            None,
        )

        schedule = evidence.schedule_snapshots[0]
        self.assertEqual(client.zone_calls, 0)
        self.assertEqual(schedule.photo_import_status, "missing")
        self.assertEqual(schedule.photo_import_reason, "config_path_unavailable")

    def test_rejects_bad_content_type_and_oversized_image(self) -> None:
        client = self._client()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(
                photo_import.urllib.request,
                "urlopen",
                return_value=_ImageResponse(b"not image", content_type="text/plain"),
            ):
                bad_type = photo_import.import_rachio_zone_photo(
                    client=client,
                    zone_id="zone-1",
                    config_path=lambda *parts: str(root.joinpath(*parts)),
                    import_enabled=True,
                )
            with patch.object(
                photo_import.urllib.request,
                "urlopen",
                return_value=_ImageResponse(
                    b"",
                    content_type="image/jpeg",
                    content_length=photo_import.MAX_IMAGE_BYTES + 1,
                ),
            ):
                oversized = photo_import.import_rachio_zone_photo(
                    client=client,
                    zone_id="zone-2",
                    config_path=lambda *parts: str(root.joinpath(*parts)),
                    import_enabled=True,
                )

        self.assertEqual(bad_type.status, "rejected")
        self.assertIn("unsupported_content_type", bad_type.reason or "")
        self.assertEqual(oversized.status, "rejected")
        self.assertEqual(oversized.reason, "image_too_large")

    def test_rejects_oversized_image_without_content_length_after_capped_read(self) -> None:
        client = self._client()
        oversized_payload = b"x" * (photo_import.MAX_IMAGE_BYTES + 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(
                photo_import.urllib.request,
                "urlopen",
                return_value=_ImageResponse(
                    oversized_payload,
                    content_type="image/jpeg",
                    include_content_length=False,
                ),
            ):
                result = photo_import.import_rachio_zone_photo(
                    client=client,
                    zone_id="zone-1",
                    config_path=lambda *parts: str(root.joinpath(*parts)),
                    import_enabled=True,
                )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason, "image_too_large")


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
        coordinator.data = types.SimpleNamespace(site_name="Demo Site")
        hass = types.SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        call = types.SimpleNamespace(data={"site_name": "Demo Site", "rule_id": "rule-1"})

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
        coordinator.data = types.SimpleNamespace(site_name="Demo Site")
        hass = types.SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        call = types.SimpleNamespace(data={"site_name": "Demo Site", "rule_id": "rule-1"})

        asyncio.run(integration_init._async_handle_clear_flow_alert_review(hass, call))

        self.assertEqual(coordinator._acknowledged_flow_alert_ids, {"rule-1"})
        self.assertEqual(refreshed, ["called"])


class ServiceRegistrationTests(unittest.TestCase):
    def test_evaluate_now_service_handler_accepts_home_assistant_call_shape(self) -> None:
        refreshed: list[str] = []
        forced: list[str] = []

        class _FakeServices:
            def __init__(self) -> None:
                self.handlers: dict[tuple[str, str], object] = {}
                self.removed: list[tuple[str, str]] = []

            def has_service(self, _domain: str, _service: str) -> bool:
                return False

            def async_register(self, domain: str, service: str, handler, schema=None) -> None:
                self.handlers[(domain, service)] = handler

            def async_remove(self, domain: str, service: str) -> None:
                self.removed.append((domain, service))

        async def _refresh() -> None:
            refreshed.append("called")

        services = _FakeServices()
        coordinator = types.SimpleNamespace(
            async_request_refresh=_refresh,
            force_next_reconciliation=lambda: forced.append("called"),
        )
        hass = types.SimpleNamespace(
            services=services,
            data={DOMAIN: {"entry-1": coordinator}},
        )

        remove = integration_init._async_register_services(hass)
        handler = services.handlers[(DOMAIN, "evaluate_now")]
        asyncio.run(handler(types.SimpleNamespace(data={})))

        self.assertEqual(refreshed, ["called"])
        self.assertEqual(forced, ["called"])
        remove()
        self.assertIn((DOMAIN, "evaluate_now"), services.removed)


class BulkMoistureServiceTests(unittest.TestCase):
    def _schedule(
        self,
        *,
        rule_id: str,
        name: str,
        recommended_action: str,
        review_state: str,
        write_value: str | None,
    ) -> ScheduleSnapshot:
        return ScheduleSnapshot(
            rule_id=rule_id,
            name=name,
            status="idle",
            reason="none",
            catch_up_candidate="not_needed",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id=f"switch.{rule_id}",
            zone_entity_id=f"switch.zone_{rule_id}",
            controller_zone_id=f"zone-{rule_id}",
            moisture_entity_id=f"sensor.moisture_{rule_id}",
            moisture_value=write_value,
            moisture_band="dry" if write_value else "missing",
            moisture_status="ok",
            moisture_write_back_ready="ready",
            recommended_action=recommended_action,
            review_state=review_state,
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
            write_value=write_value,
            moisture_freshness="fresh" if write_value else "expired",
            moisture_confidence="low" if write_value else "none",
            moisture_observed_value=write_value,
            moisture_observed_at="2026-05-10T02:12:51+00:00" if write_value else None,
            moisture_age_label="4h" if write_value else "unknown",
        )

    def test_write_recommended_moisture_writes_only_ready_recommendations(self) -> None:
        calls: list[tuple[str, float]] = []
        records: list[dict[str, object]] = []
        refreshes: list[str] = []
        schedules = (
            self._schedule(
                rule_id="one",
                name="Dry schedule",
                recommended_action="write_moisture_now",
                review_state="pending_review",
                write_value="13",
            ),
            self._schedule(
                rule_id="two",
                name="Watch schedule",
                recommended_action="none",
                review_state="none",
                write_value="58",
            ),
        )

        class _Client:
            def __init__(self, _token: str) -> None:
                pass

            def set_zone_moisture_percent(self, zone_id: str, value: float) -> None:
                calls.append((zone_id, value))

        async def _executor(func, *args):
            return func(*args)

        async def _refresh() -> None:
            refreshes.append("called")

        coordinator = SimpleNamespace(
            data=SimpleNamespace(
                site_name="Demo Site",
                rachio_config_entry_id="entry-1",
                schedule_snapshots=schedules,
            ),
            entry=SimpleNamespace(
                data={"allow_moisture_write_back": True},
                options={},
            ),
            record_moisture_write=lambda **kwargs: records.append(kwargs),
            async_request_refresh=_refresh,
        )
        hass = SimpleNamespace(
            data={DOMAIN: {"entry-1": coordinator}},
            config_entries=SimpleNamespace(
                async_get_entry=lambda _entry_id: SimpleNamespace(
                    data={"api_key": "token"}
                )
            ),
            async_add_executor_job=_executor,
        )

        with patch.object(integration_init, "RachioClient", _Client):
            asyncio.run(
                integration_init._async_handle_write_recommended_moisture_now(
                    hass,
                    SimpleNamespace(data={}),
                )
            )

        self.assertEqual(calls, [("zone-one", 13.0)])
        self.assertEqual(records[0]["status"], "bulk_written")
        self.assertEqual(records[0]["rule_id"], "one")
        self.assertEqual(refreshes, ["called"])

    def test_acknowledge_all_marks_only_pending_runtime_recommendations(self) -> None:
        acks: list[tuple[str, bool]] = []
        refreshes: list[str] = []
        schedules = (
            self._schedule(
                rule_id="one",
                name="Dry schedule",
                recommended_action="write_moisture_now",
                review_state="pending_review",
                write_value="13",
            ),
            self._schedule(
                rule_id="two",
                name="Watch schedule",
                recommended_action="none",
                review_state="none",
                write_value="58",
            ),
        )

        async def _refresh() -> None:
            refreshes.append("called")

        coordinator = SimpleNamespace(
            data=SimpleNamespace(site_name="Demo Site", schedule_snapshots=schedules),
            set_recommendation_acknowledged=lambda **kwargs: acks.append(
                (kwargs["rule_id"], kwargs["acknowledged"])
            ),
            async_request_refresh=_refresh,
        )
        hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})

        asyncio.run(
            integration_init._async_handle_acknowledge_all_recommendations(
                hass,
                SimpleNamespace(data={}),
            )
        )

        self.assertEqual(acks, [("one", True)])
        self.assertEqual(refreshes, ["called"])


class QuickRunServiceTests(unittest.TestCase):
    def test_quick_run_zone_calls_rachio_start_watering(self) -> None:
        calls: list[tuple[str, str, dict, bool]] = []
        refreshes: list[str] = []
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
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="none",
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
            imported_image_path="/local/rachio-supervisor/imported-zones/zone-1.jpg",
            rachio_image_available=True,
            photo_import_status="cached",
            photo_import_reason="imageUrl_missing",
        )

        async def _service_call(domain: str, service: str, data: dict, *, blocking: bool):
            calls.append((domain, service, data, blocking))

        async def _refresh() -> None:
            refreshes.append("called")

        coordinator = SimpleNamespace(
            data=SimpleNamespace(
                site_name="Demo Site",
                schedule_snapshots=(schedule,),
            ),
            async_request_refresh=_refresh,
        )
        hass = SimpleNamespace(
            data={DOMAIN: {"entry-1": coordinator}},
            services=SimpleNamespace(async_call=_service_call),
        )

        asyncio.run(
            integration_init._async_handle_quick_run_zone(
                hass,
                SimpleNamespace(
                    data={"zone_entity_id": "switch.zone_pots", "duration_minutes": 8}
                ),
            )
        )

        self.assertEqual(
            calls,
            [
                (
                    "rachio",
                    "start_watering",
                    {
                        "entity_id": "switch.zone_pots",
                        "duration": 8,
                    },
                    True,
                )
            ],
        )
        self.assertEqual(refreshes, ["called"])

    def test_quick_run_zone_clamps_minutes_before_calling_rachio(self) -> None:
        calls: list[tuple[str, str, dict, bool]] = []
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
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="none",
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
            imported_image_path="/local/rachio-supervisor/imported-zones/zone-1.jpg",
            rachio_image_available=True,
            photo_import_status="cached",
            photo_import_reason="imageUrl_missing",
        )

        async def _service_call(domain: str, service: str, data: dict, *, blocking: bool):
            calls.append((domain, service, data, blocking))

        async def _refresh() -> None:
            return None

        coordinator = SimpleNamespace(
            data=SimpleNamespace(site_name="Demo Site", schedule_snapshots=(schedule,)),
            async_request_refresh=_refresh,
        )
        hass = SimpleNamespace(
            data={DOMAIN: {"entry-1": coordinator}},
            services=SimpleNamespace(async_call=_service_call),
        )

        asyncio.run(
            integration_init._async_handle_quick_run_zone(
                hass,
                SimpleNamespace(
                    data={"schedule_name": "Pots - Dawn Micro", "duration_minutes": 120}
                ),
            )
        )

        self.assertEqual(calls[0][2]["duration"], 60)


class CatchUpCutoverTests(unittest.TestCase):
    def _schedule(
        self,
        *,
        name: str = "Driveway Hedge",
        policy_mode: str = "auto_catch_up_enabled",
        catch_up_candidate: str = "eligible_auto",
        zone_entity_id: str | None = "switch.zone_driveway",
    ) -> ScheduleSnapshot:
        return ScheduleSnapshot(
            rule_id="rule-driveway",
            name=name,
            status="skipped_recently",
            reason="Observed rain was below the skip threshold.",
            catch_up_candidate=catch_up_candidate,
            policy_mode=policy_mode,
            policy_basis="Configured automatic catch-up opt-in.",
            schedule_entity_id="switch.schedule_driveway",
            zone_entity_id=zone_entity_id,
            controller_zone_id="zone-driveway",
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="clear",
            runtime_minutes=9,
            last_run_at=None,
            last_skip_at="2026-05-10T06:00:00+10:00",
            summary="Driveway Hedge was skipped with insufficient observed rain.",
            threshold_mm=6.35,
            observed_mm=1.0,
        )

    def _confirmed_decision(self) -> dict[str, object]:
        return {
            "status": "confirmed",
            "reason": "confirmed_skip",
            "schedule_name": "Driveway Hedge",
            "zone_label": "switch.zone_driveway",
            "zone_entity_id": "switch.zone_driveway",
            "runtime_minutes": 9,
            "summary": "Driveway Hedge was skipped with insufficient observed rain.",
            "decision_key": "rule-driveway|2026-05-10T06:00:00+10:00",
            "event_id": None,
            "decision_at": "2026-05-10T07:00:00+10:00",
        }

    def _coordinator(self, calls: list[tuple[str, str, dict, bool]]) -> RachioSupervisorCoordinator:
        async def _service_call(domain: str, service: str, data: dict, *, blocking: bool):
            calls.append((domain, service, data, blocking))

        coordinator = object.__new__(RachioSupervisorCoordinator)
        coordinator.hass = SimpleNamespace(
            services=SimpleNamespace(async_call=_service_call)
        )
        coordinator._lockouts = {}
        coordinator._latest_catch_up_decision = {
            "status": "not_needed",
            "reason": "monitoring",
            "schedule_name": None,
            "zone_label": None,
            "runtime_minutes": 0,
            "summary": "No active catch-up candidate.",
            "decision_key": "monitoring",
            "event_id": None,
            "decision_at": None,
        }
        return coordinator

    def test_automatic_catch_up_uses_integer_rachio_duration(self) -> None:
        calls: list[tuple[str, str, dict, bool]] = []
        coordinator = self._coordinator(calls)

        executed = asyncio.run(
            coordinator._async_execute_catch_up_decision(
                self._confirmed_decision(),
                current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
                source="automatic_supervision",
            )
        )

        self.assertEqual(executed["status"], "executed")
        self.assertEqual(executed["execution_source"], "automatic_supervision")
        self.assertEqual(
            calls,
            [
                (
                    "rachio",
                    "start_watering",
                    {"entity_id": "switch.zone_driveway", "duration": 9},
                    True,
                )
            ],
        )

    def test_observe_first_keeps_confirmed_decision_without_watering(self) -> None:
        decision = evaluate_catch_up_decision(
            current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
            schedules=(self._schedule(),),
            controller_available=True,
            rain_active=False,
            rain_delay_active=False,
            standby_active=False,
            safe_window_end_hour=8,
            lockouts={},
        )

        self.assertEqual(decision["status"], "confirmed")
        self.assertEqual(decision["schedule_name"], "Driveway Hedge")

    def test_active_supervision_only_confirms_opted_in_auto_schedule(self) -> None:
        opted_in = evaluate_catch_up_decision(
            current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
            schedules=(self._schedule(policy_mode="auto_catch_up_enabled"),),
            controller_available=True,
            rain_active=False,
            rain_delay_active=False,
            standby_active=False,
            safe_window_end_hour=8,
            lockouts={},
        )
        observe_only = evaluate_catch_up_decision(
            current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
            schedules=(
                self._schedule(
                    policy_mode="observe_only",
                    catch_up_candidate="review_recommended",
                ),
            ),
            controller_available=True,
            rain_active=False,
            rain_delay_active=False,
            standby_active=False,
            safe_window_end_hour=8,
            lockouts={},
        )

        self.assertEqual(opted_in["status"], "confirmed")
        self.assertEqual(observe_only["status"], "deferred")
        self.assertEqual(observe_only["reason"], "review_recommended")

    def test_duplicate_lockout_prevents_repeated_execution(self) -> None:
        calls: list[tuple[str, str, dict, bool]] = []
        coordinator = self._coordinator(calls)
        decision = self._confirmed_decision()

        asyncio.run(
            coordinator._async_execute_catch_up_decision(
                decision,
                current=datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
                source="automatic_supervision",
            )
        )

        with self.assertRaisesRegex(ValueError, "already executed"):
            asyncio.run(
                coordinator._async_execute_catch_up_decision(
                    decision,
                    current=datetime.fromisoformat("2026-05-10T07:01:00+10:00"),
                    source="automatic_supervision",
                )
            )
        self.assertEqual(len(calls), 1)

    def test_safety_states_defer_catch_up(self) -> None:
        base = {
            "current": datetime.fromisoformat("2026-05-10T07:00:00+10:00"),
            "schedules": (self._schedule(),),
            "safe_window_end_hour": 8,
            "lockouts": {},
        }
        cases = (
            ({"controller_available": False, "rain_active": False, "rain_delay_active": False, "standby_active": False}, "controller_unavailable"),
            ({"controller_available": True, "rain_active": False, "rain_delay_active": False, "standby_active": True}, "controller_unavailable"),
            ({"controller_available": True, "rain_active": True, "rain_delay_active": False, "standby_active": False}, "rain_satisfied"),
            ({"controller_available": True, "rain_active": False, "rain_delay_active": True, "standby_active": False}, "rain_satisfied"),
            (
                {
                    "controller_available": True,
                    "rain_active": False,
                    "rain_delay_active": False,
                    "standby_active": False,
                    "current": datetime.fromisoformat("2026-05-10T09:00:00+10:00"),
                },
                "outside_safe_window",
            ),
        )

        for overrides, reason in cases:
            payload = {**base, **overrides}
            with self.subTest(reason=reason):
                decision = evaluate_catch_up_decision(**payload)
                self.assertEqual(decision["status"], "deferred")
                self.assertEqual(decision["reason"], reason)

    def test_run_catch_up_now_executes_current_confirmed_decision(self) -> None:
        calls: list[tuple[str, str, dict, bool]] = []
        coordinator = self._coordinator(calls)
        coordinator._latest_catch_up_decision = self._confirmed_decision()
        refreshes: list[str] = []

        async def _refresh() -> None:
            refreshes.append("called")

        coordinator.async_request_refresh = _refresh

        asyncio.run(coordinator.async_run_catch_up_now())

        self.assertEqual(refreshes, ["called"])
        self.assertEqual(coordinator._latest_catch_up_decision["status"], "executed")
        self.assertEqual(calls[0][2]["duration"], 9)

    def test_run_catch_up_now_rejects_without_eligible_decision(self) -> None:
        calls: list[tuple[str, str, dict, bool]] = []
        coordinator = self._coordinator(calls)
        refreshes: list[str] = []

        async def _refresh() -> None:
            refreshes.append("called")

        coordinator.async_request_refresh = _refresh

        with self.assertRaisesRegex(ValueError, "No confirmed catch-up"):
            asyncio.run(coordinator.async_run_catch_up_now())
        self.assertEqual(calls, [])

    def test_run_catch_up_service_rejects_ambiguous_site(self) -> None:
        async def _noop() -> None:
            return None

        coordinator_a = SimpleNamespace(
            data=SimpleNamespace(site_name="A"),
            async_run_catch_up_now=_noop,
        )
        coordinator_b = SimpleNamespace(
            data=SimpleNamespace(site_name="B"),
            async_run_catch_up_now=_noop,
        )
        hass = SimpleNamespace(data={DOMAIN: {"a": coordinator_a, "b": coordinator_b}})

        with self.assertRaisesRegex(Exception, "Multiple sites"):
            asyncio.run(
                integration_init._async_handle_run_catch_up_now(
                    hass,
                    SimpleNamespace(data={}),
                )
            )


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
    def _hass_with_states(self, state_map: dict[str, object]):
        class _States:
            def get(self, entity_id: str):
                return state_map.get(entity_id)

            def async_all(self):
                return tuple(state_map.values())

        return SimpleNamespace(states=_States())

    def _moisture_schedule(self) -> ScheduleSnapshot:
        return ScheduleSnapshot(
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
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="pending_moisture_eval",
            review_state="pending",
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
        )

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

    def test_moisture_evidence_live_numeric_becomes_fresh(self) -> None:
        current = datetime.fromisoformat("2026-05-10T08:00:00+00:00")
        state_map = {
            "sensor.pots_soil_moisture": SimpleNamespace(
                entity_id="sensor.pots_soil_moisture",
                state="23",
                attributes={},
                last_updated=datetime.fromisoformat("2026-05-10T04:00:00+00:00"),
            ),
            "sensor.pots_soil_sampling": SimpleNamespace(
                entity_id="sensor.pots_soil_sampling",
                state="30",
                attributes={},
                last_updated=current,
            ),
        }

        evidence = resolve_moisture_evidence(
            self._hass_with_states(state_map),
            "sensor.pots_soil_moisture",
            cache={},
            current=current,
        )

        self.assertEqual(evidence.observed_value, "23")
        self.assertEqual(evidence.freshness, "fresh")
        self.assertEqual(evidence.confidence, "high")
        self.assertEqual(evidence.sampling_interval_seconds, 30)

    def test_moisture_evidence_unknown_uses_recent_cached_value(self) -> None:
        current = datetime.fromisoformat("2026-05-10T12:00:00+00:00")
        cache = {
            "sensor.pots_moisture": MoistureEvidenceCacheEntry(
                observed_value="24",
                observed_at="2026-05-10T00:00:00+00:00",
            )
        }
        state_map = {
            "sensor.pots_moisture": SimpleNamespace(
                entity_id="sensor.pots_moisture",
                state="unknown",
                attributes={},
                last_updated=current,
            )
        }

        evidence = resolve_moisture_evidence(
            self._hass_with_states(state_map),
            "sensor.pots_moisture",
            cache=cache,
            current=current,
        )

        self.assertEqual(evidence.observed_value, "24")
        self.assertEqual(evidence.freshness, "recent")
        self.assertIn("sensor_sleeping_or_offline", evidence.quality_flags)
        self.assertEqual(evidence.quality_note, "sensor_sleeping_or_offline")

    def test_moisture_evidence_cached_36_hours_is_stale(self) -> None:
        current = datetime.fromisoformat("2026-05-10T12:00:00+00:00")
        cache = {
            "sensor.pots_moisture": MoistureEvidenceCacheEntry(
                observed_value="24",
                observed_at="2026-05-09T00:00:00+00:00",
            )
        }

        evidence = resolve_moisture_evidence(
            self._hass_with_states({}),
            "sensor.pots_moisture",
            cache=cache,
            current=current,
        )

        self.assertEqual(evidence.freshness, "stale")
        self.assertEqual(evidence.quality_note, "missing_sensor")
        self.assertIn("stale_sample", evidence.quality_flags)

    def test_moisture_evidence_cached_80_hours_is_expired(self) -> None:
        current = datetime.fromisoformat("2026-05-10T12:00:00+00:00")
        cache = {
            "sensor.pots_moisture": MoistureEvidenceCacheEntry(
                observed_value="24",
                observed_at="2026-05-07T04:00:00+00:00",
            )
        }

        evidence = resolve_moisture_evidence(
            self._hass_with_states({}),
            "sensor.pots_moisture",
            cache=cache,
            current=current,
        )

        self.assertEqual(evidence.freshness, "expired")
        self.assertIn("expired_sample", evidence.quality_flags)
        self.assertEqual(evidence.confidence, "none")

    def test_moisture_evidence_repeated_zero_marks_boundary_calibration(self) -> None:
        cache: dict[str, MoistureEvidenceCacheEntry] = {}
        first = self._hass_with_states(
            {
                "sensor.pots_moisture": SimpleNamespace(
                    entity_id="sensor.pots_moisture",
                    state="0",
                    attributes={},
                    last_updated=datetime.fromisoformat("2026-05-10T06:00:00+00:00"),
                )
            }
        )
        second = self._hass_with_states(
            {
                "sensor.pots_moisture": SimpleNamespace(
                    entity_id="sensor.pots_moisture",
                    state="0",
                    attributes={},
                    last_updated=datetime.fromisoformat("2026-05-10T06:30:00+00:00"),
                )
            }
        )

        resolve_moisture_evidence(
            first,
            "sensor.pots_moisture",
            cache=cache,
            current=datetime.fromisoformat("2026-05-10T06:05:00+00:00"),
        )
        evidence = resolve_moisture_evidence(
            second,
            "sensor.pots_moisture",
            cache=cache,
            current=datetime.fromisoformat("2026-05-10T06:35:00+00:00"),
        )

        self.assertIn("boundary_value_needs_calibration", evidence.quality_flags)
        self.assertEqual(evidence.quality_note, "boundary_value_needs_calibration")

    def test_moisture_evidence_nonnumeric_keeps_last_valid_inside_window(self) -> None:
        current = datetime.fromisoformat("2026-05-10T12:00:00+00:00")
        cache = {
            "sensor.pots_moisture": MoistureEvidenceCacheEntry(
                observed_value="22",
                observed_at="2026-05-10T08:00:00+00:00",
            )
        }
        state_map = {
            "sensor.pots_moisture": SimpleNamespace(
                entity_id="sensor.pots_moisture",
                state="dry",
                attributes={},
                last_updated=current,
            )
        }

        evidence = resolve_moisture_evidence(
            self._hass_with_states(state_map),
            "sensor.pots_moisture",
            cache=cache,
            current=current,
        )

        self.assertEqual(evidence.observed_value, "22")
        self.assertEqual(evidence.freshness, "fresh")
        self.assertEqual(evidence.quality_note, "non_numeric_state")

    def test_moisture_evidence_missing_sensor_has_no_sample(self) -> None:
        evidence = resolve_moisture_evidence(
            self._hass_with_states({}),
            "sensor.missing_moisture",
            cache={},
            current=datetime.fromisoformat("2026-05-10T12:00:00+00:00"),
        )

        self.assertIsNone(evidence.observed_value)
        self.assertEqual(evidence.quality_note, "missing_sensor")
        self.assertEqual(evidence.confidence, "none")

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
            moisture_last_updated="2026-05-10T02:12:51+00:00",
            moisture_observed_value="58",
            moisture_observed_at="2026-05-10T02:12:51+00:00",
            moisture_age_label="4h",
            moisture_freshness="fresh",
            moisture_confidence="low",
            moisture_source_state="58",
            moisture_source_last_updated="2026-05-10T02:12:51+00:00",
            moisture_source_age_label="4h",
        )

        items = build_moisture_review_items((schedule,))

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["schedule_name"], "Rear Protea Shade Bed")
        self.assertEqual(items[0]["moisture_band"], "wet")
        self.assertEqual(items[0]["recommended_action"], "none")
        self.assertEqual(items[0]["recommended_action_label"], "No write needed")
        self.assertEqual(items[0]["data_quality"], "ok")
        self.assertEqual(items[0]["moisture_quality_label"], "Evidence ok")
        self.assertEqual(items[0]["last_check_in_label"], "Last check-in: 4h ago")
        self.assertEqual(
            items[0]["last_valid_moisture_label"],
            "Last valid: 58% - 4h ago",
        )
        self.assertEqual(
            items[0]["sensor_evidence_label"],
            "Last check-in: 4h ago - Last valid: 58% - 4h ago",
        )
        self.assertEqual(
            items[0]["moisture_last_updated"],
            "2026-05-10T02:12:51+00:00",
        )
        self.assertEqual(items[0]["write_summary"], "Sensor 58% -> Rachio zone moisture")
        self.assertEqual(items[0]["write_status_label"], "Manual write ready")
        self.assertEqual(items[0]["rachio_moisture_value"], "not_reported")
        self.assertTrue(items[0]["can_write"])

    def test_moisture_review_item_uses_recent_confirmation_copy(self) -> None:
        schedule = self._moisture_schedule()
        hydrated = replace(
            schedule,
            moisture_entity_id="sensor.pots_moisture",
            moisture_value="13",
            moisture_band="dry",
            moisture_status="ok",
            recommended_action="write_moisture_now",
            review_state="pending_review",
            write_value="13",
            moisture_observed_value="13",
            moisture_observed_at="2026-05-10T00:00:00+00:00",
            moisture_age_label="12h",
            moisture_freshness="recent",
            moisture_confidence="medium",
            moisture_source_state="13",
            moisture_source_last_updated="2026-05-10T00:00:00+00:00",
            moisture_source_age_label="12h",
        )

        item = build_moisture_review_items((hydrated,))[0]

        self.assertEqual(item["posture_note"], "Recent sample - confirm before write")
        self.assertEqual(item["moisture_age_label"], "12h")
        self.assertEqual(item["moisture_confidence"], "medium")
        self.assertEqual(item["last_check_in_label"], "Last check-in: 12h ago")
        self.assertEqual(item["write_status_label"], "Manual write ready")

    def test_moisture_review_item_prefers_last_check_in_for_sleeping_sensor(self) -> None:
        schedule = self._moisture_schedule()
        sleeping = replace(
            schedule,
            name="Boxwood + Liriope",
            moisture_entity_id="sensor.boxwoods_liriopes_soil_moisture",
            moisture_band="missing",
            moisture_status="unavailable",
            recommended_action="none",
            review_state="clear",
            moisture_source_state="unknown",
            moisture_source_last_updated="2026-05-11T11:04:41+00:00",
            moisture_source_age_label="2d",
            moisture_freshness="expired",
            moisture_quality_note="expired_sample",
            moisture_quality_flags=(
                "sensor_sleeping_or_offline",
                "expired_sample",
            ),
            write_summary="No usable moisture value to write",
        )

        item = build_moisture_review_items((sleeping,))[0]

        self.assertEqual(item["posture_note"], "Sensor offline")
        self.assertEqual(item["last_check_in_label"], "Last check-in: 2d ago")
        self.assertEqual(item["last_valid_moisture_label"], "Last valid: none")
        self.assertEqual(
            item["sensor_evidence_label"],
            "Last check-in: 2d ago - Last valid: none",
        )
        self.assertEqual(item["moisture_quality_label"], "No recent moisture sample")
        self.assertEqual(
            item["write_status_label"],
            "No write needed - No usable moisture value to write",
        )
        self.assertFalse(item["can_write"])

    def test_rain_actuals_accepts_numeric_sensor(self) -> None:
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: SimpleNamespace(
                    state="12.5",
                    attributes={"unit_of_measurement": "mm"},
                )
                if entity_id == "sensor.rain_24h"
                else None
            )
        )

        result = resolve_rain_actuals_entity(
            hass,
            "sensor.rain_24h",
        )

        self.assertEqual(result.value, "12.5")
        self.assertEqual(result.unit, "mm")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.window, "24h")
        self.assertEqual(result.confidence, "high")
        self.assertIsNone(result.missing_input)
        self.assertIn("numeric", result.reason)

    def test_rain_actuals_rejects_forecast_only_weather(self) -> None:
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: SimpleNamespace(
                    state="rainy",
                    attributes={"precipitation_unit": "mm"},
                )
                if entity_id == "weather.home"
                else None
            )
        )

        result = resolve_rain_actuals_entity(
            hass,
            "weather.home",
        )

        self.assertEqual(result.value, "not_reported")
        self.assertEqual(result.unit, "mm")
        self.assertEqual(result.status, "weather_no_observed_precipitation")
        self.assertEqual(result.window, "forecast_only")
        self.assertEqual(
            result.missing_input,
            "rain_actuals_weather_no_observed_precipitation",
        )
        self.assertIn("does not expose", result.reason)

    def test_rain_actuals_accepts_willyweather_style_attributes(self) -> None:
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: SimpleNamespace(
                    state="cloudy",
                    attributes={
                        "rain_since_9am": "17.2",
                        "precipitation_unit": "mm",
                    },
                )
                if entity_id == "weather.willyweather"
                else None
            )
        )

        result = resolve_rain_actuals_entity(hass, "weather.willyweather")

        self.assertEqual(result.value, "17.2")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.window, "since_9am")
        self.assertEqual(result.confidence, "medium")

    def test_rain_actuals_accepts_weather_underground_precip_total(self) -> None:
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: SimpleNamespace(
                    state="observing",
                    attributes={"precipTotal": "4.6", "precipitation_unit": "mm"},
                )
                if entity_id == "weather.pws"
                else None
            )
        )

        result = resolve_rain_actuals_entity(hass, "weather.pws")

        self.assertEqual(result.value, "4.6")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.window, "today")

    def test_weather_underground_pws_source_resolves_precip_total(self) -> None:
        payload = (
            b'{"observations":[{"stationID":"KCAEXAMP1",'
            b'"obsTimeLocal":"2026-05-14 11:45:32",'
            b'"metric":{"precipTotal":2.4,"precipRate":0.0}}]}'
        )

        with patch.object(
            coordinator_module.urllib.request,
            "urlopen",
            return_value=_ImageResponse(payload, content_type="application/json"),
        ):
            result = resolve_weather_underground_pws_actuals("kcaexamp1", "api-key")

        self.assertEqual(result.value, "2.4")
        self.assertEqual(result.unit, "mm")
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.window, "today")
        self.assertEqual(result.confidence, "medium")
        self.assertEqual(result.source_type, "weather_underground_pws")
        self.assertEqual(result.source_id, "weather_underground_pws:KCAEXAMP1")
        self.assertEqual(result.observed_at, "2026-05-14 11:45:32")

    def test_weather_underground_pws_source_requires_api_key(self) -> None:
        result = resolve_weather_underground_pws_actuals("KCAEXAMP1", "")

        self.assertEqual(result.status, "api_key_missing")
        self.assertEqual(
            result.missing_input,
            "rain_actuals_weather_station_api_key_missing",
        )

    def test_rain_candidate_discovery_finds_numeric_rain_sensor(self) -> None:
        states: dict[str, object] = {
            "sensor.backyard_rain_24h": SimpleNamespace(
                entity_id="sensor.backyard_rain_24h",
                state="8.1",
                attributes={
                    "friendly_name": "Backyard Rain 24h",
                    "device_class": "precipitation",
                    "unit_of_measurement": "mm",
                },
            ),
            "sensor.temperature": SimpleNamespace(
                entity_id="sensor.temperature",
                state="21",
                attributes={"friendly_name": "Temperature", "unit_of_measurement": "C"},
            ),
        }
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: states.get(entity_id),
                async_all=lambda: list(states.values()),
            )
        )

        candidates = discover_rain_source_candidates(
            hass,
            selected_entity_id="sensor.backyard_rain_24h",
        )

        self.assertEqual(candidates[0]["entity_id"], "sensor.backyard_rain_24h")
        self.assertEqual(candidates[0]["status"], "ok")
        self.assertTrue(candidates[0]["selected"])

    def test_rain_candidate_discovery_filters_supervisor_and_helper_noise(self) -> None:
        states: dict[str, object] = {
            "sensor.rachio_site_actual_rain_24h": SimpleNamespace(
                entity_id="sensor.rachio_site_actual_rain_24h",
                state="unconfigured",
                attributes={"friendly_name": "Rachio Site Actual rain, 24h"},
            ),
            "input_text.sugarloaf_irrigation_rain_catch_up_state": SimpleNamespace(
                entity_id="input_text.sugarloaf_irrigation_rain_catch_up_state",
                state="2026-05-11 07:26|deferred|lawn|rain_satisfied",
                attributes={"friendly_name": "Sugarloaf Irrigation Rain Catch-up State"},
            ),
            "automation.sugarloaf_irrigation_rain_catch_up_lawn": SimpleNamespace(
                entity_id="automation.sugarloaf_irrigation_rain_catch_up_lawn",
                state="off",
                attributes={"friendly_name": "Sugarloaf Irrigation Rain Catch-up - Lawn"},
            ),
            "sensor.backyard_rain_24h": SimpleNamespace(
                entity_id="sensor.backyard_rain_24h",
                state="3.2",
                attributes={
                    "friendly_name": "Backyard Rain 24h",
                    "device_class": "precipitation",
                    "unit_of_measurement": "mm",
                },
            ),
        }
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: states.get(entity_id),
                async_all=lambda: list(states.values()),
            )
        )

        candidates = discover_rain_source_candidates(hass)

        self.assertEqual([item["entity_id"] for item in candidates], ["sensor.backyard_rain_24h"])

    def test_rachio_weather_probe_is_diagnostic_only(self) -> None:
        probe = build_rachio_weather_probe(
            {
                "id": "controller-1",
                "weatherStationId": "station-1",
                "weatherSource": "pws",
            },
            {"provider": "forecast-provider", "rain": {"amount": 4}},
        )

        self.assertEqual(probe["status"], "forecast_available")
        self.assertFalse(probe["used_for_actual_rain"])
        paths = [hint["path"] for hint in probe["hints"]]
        self.assertIn("controller.weatherStationId", paths)

    def test_rachio_weather_outlook_summarizes_forecast_without_actual_rain(self) -> None:
        outlook = build_rachio_weather_outlook(
            {
                "current": {
                    "weatherSummary": "Showers",
                    "temperature": 18.2,
                    "precipIntensity": 0.61,
                    "precipProbability": 0.49,
                },
                "forecast": [
                    {"weatherSummary": "Showers", "calculatedPrecip": 0.05},
                    {"weatherSummary": "Mostly Sunny", "calculatedPrecip": 0.0},
                ],
            }
        )

        self.assertEqual(outlook["status"], "forecast_available")
        self.assertFalse(outlook["used_for_actual_rain"])
        self.assertEqual(outlook["heat_assist_state"], "weather_outlook_only")
        self.assertIn("Now: Showers", outlook["summary"])
        self.assertIn("Next: Mostly Sunny", outlook["summary"])

    def test_catch_up_evidence_and_action_labels_use_rain_amount(self) -> None:
        schedule = ScheduleSnapshot(
            rule_id="rule-front",
            name="Front Lower Mixed Bed",
            status="skipped_recently",
            reason="skip",
            catch_up_candidate="review_recommended",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id="switch.schedule_front",
            zone_entity_id="switch.zone_front",
            controller_zone_id="zone-front",
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="clear",
            runtime_minutes=45,
            last_run_at=None,
            last_skip_at="2026-05-06T02:01:00+10:00",
            summary="Front skipped with low observed rain.",
            threshold_mm=6.35,
            observed_mm=0.17,
        )
        decision = {
            "status": "deferred",
            "reason": "review_recommended",
            "schedule_name": "Front Lower Mixed Bed",
        }

        evidence = build_catch_up_evidence_label(
            decision=decision,
            schedules=(schedule,),
            observed_rain_best_event=None,
            actual_rain_value="unconfigured",
            actual_rain_unit=None,
            actual_rain_window="unconfigured",
        )
        action = build_catch_up_action_label(
            status="deferred",
            reason="review_recommended",
            schedule_name="Front Lower Mixed Bed",
            runtime_minutes=45,
        )

        self.assertIn("0.17 mm", evidence)
        self.assertIn("2026-05-06", evidence)
        self.assertIn("Review catch-up", action)

    def test_schedule_rule_metadata_discovers_zone_days_and_next_run(self) -> None:
        controller = {
            "timeZone": "Australia/Melbourne",
            "zones": [{"id": "zone-grass", "name": "Grass", "enabled": True}],
        }
        rule = {
            "name": "Lawn - Summer Green",
            "enabled": True,
            "zones": [{"zoneId": "zone-grass", "duration": 3600}],
            "scheduleJobTypes": ["DAY_OF_WEEK_2", "DAY_OF_WEEK_5"],
            "startHour": 2,
            "startMinute": 0,
        }
        linked = LinkedRachioEntities(
            connectivity_entity_id=None,
            rain_entity_id=None,
            rain_delay_entity_id=None,
            standby_entity_id=None,
            zone_switches=("switch.rachio_grass",),
            schedule_switches=(),
            zone_entities=(
                ZoneEntityRef("switch.rachio_grass", "Rachio Controller Grass", None),
            ),
            schedule_entities=(),
            all_entities=("switch.rachio_grass",),
        )

        zone_id = match_controller_zone_from_rule(rule, controller)
        zone_entity = match_zone_entity_by_controller_zone(zone_id, controller, linked)
        next_run = schedule_rule_next_run(
            rule,
            controller,
            current=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(zone_id, "zone-grass")
        self.assertEqual(zone_entity.entity_id, "switch.rachio_grass")
        self.assertEqual(schedule_rule_watering_days(rule), ("T", "F"))
        self.assertTrue(next_run.startswith("2026-05-12T02:00:00"))

    def test_rachio_evidence_matches_schedule_to_zone_id_before_name_guess(self) -> None:
        class _Client:
            def list_person_devices(self):
                return [
                    {
                        "id": "device-1",
                        "name": "Rachio Controller",
                        "timeZone": "Australia/Melbourne",
                        "zones": [
                            {"id": "zone-grass", "name": "Grass", "enabled": True}
                        ],
                        "scheduleRules": [
                            {
                                "id": "rule-lawn",
                                "name": "Lawn - Summer Green",
                                "enabled": True,
                                "zones": [{"zoneId": "zone-grass", "duration": 3600}],
                                "scheduleJobTypes": ["DAY_OF_WEEK_2", "DAY_OF_WEEK_5"],
                                "startHour": 2,
                                "startMinute": 0,
                                "totalDuration": 3600,
                            }
                        ],
                    }
                ]

            def list_device_events(self, *_args, **_kwargs):
                return []

            def list_device_webhooks(self, _device_id):
                return []

        linked = LinkedRachioEntities(
            connectivity_entity_id=None,
            rain_entity_id=None,
            rain_delay_entity_id=None,
            standby_entity_id=None,
            zone_switches=("switch.rachio_grass",),
            schedule_switches=("switch.rachio_lawn_summer_green_schedule",),
            zone_entities=(
                ZoneEntityRef("switch.rachio_grass", "Rachio Controller Grass", None),
            ),
            schedule_entities=(
                ScheduleEntityRef(
                    "switch.rachio_lawn_summer_green_schedule",
                    "Lawn - Summer Green Schedule",
                    None,
                ),
            ),
            all_entities=(
                "switch.rachio_grass",
                "switch.rachio_lawn_summer_green_schedule",
            ),
        )

        evidence = build_rachio_evidence(
            _Client(),
            linked,
            1,
            True,
            "Rachio",
            None,
            None,
            set(),
            set(),
            set(),
        )

        schedule = evidence.schedule_snapshots[0]
        self.assertEqual(schedule.controller_zone_id, "zone-grass")
        self.assertEqual(schedule.zone_entity_id, "switch.rachio_grass")
        self.assertEqual(schedule.watering_days, ("T", "F"))
        self.assertTrue(schedule.next_run_at)

    def test_interval_schedule_next_run_uses_rachio_start_date(self) -> None:
        controller = {"timeZone": "Australia/Melbourne", "zones": []}
        rule = {
            "scheduleJobTypes": ["INTERVAL_14"],
            "startDate": 1778248800000,
            "startHour": 2,
            "startMinute": 0,
            "summary": "Every 14 days at 2:00 AM",
        }

        next_run = schedule_rule_next_run(
            rule,
            controller,
            current=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        )

        self.assertTrue(next_run.startswith("2026-05-23T02:00:00"))

    def test_zone_overview_uses_rule_metadata_and_does_not_invent_plant_note(self) -> None:
        schedule = ScheduleSnapshot(
            rule_id="rule-1",
            name="Lawn - Summer Green",
            status="monitoring",
            reason="watching",
            catch_up_candidate="not_applicable",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id="switch.schedule_lawn",
            zone_entity_id="switch.zone_grass",
            controller_zone_id="zone-grass",
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="clear",
            runtime_minutes=60,
            last_run_at=None,
            last_skip_at=None,
            summary="Every Tue, Fri at 2:00 AM",
            threshold_mm=None,
            observed_mm=None,
            next_run_at="2026-05-12T02:00:00+10:00",
            watering_days=("T", "F"),
        )
        hass = SimpleNamespace(states=SimpleNamespace(get=lambda entity_id: None))

        items = build_zone_overview_items(hass, (schedule,))

        self.assertEqual(items[0]["next_run"], "2026-05-12T02:00:00+10:00")
        self.assertEqual(items[0]["watering_days"], ["T", "F"])
        self.assertEqual(items[0]["plant_note"], "")

    def test_zone_overview_items_are_visual_zone_payloads(self) -> None:
        schedule = ScheduleSnapshot(
            rule_id="rule-1",
            name="Pots - Dawn Micro",
            status="completed_recently",
            reason="ran",
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
            last_run_at="2026-05-10T06:00:00+10:00",
            last_skip_at=None,
            summary="ran",
            threshold_mm=None,
            observed_mm=None,
        )
        state_map = {
            "switch.schedule_pots": SimpleNamespace(
                state="on",
                attributes={
                    "next_run": "Tue 06:00",
                    "watering_days": ["monday", "wednesday", "friday"],
                    "plant_note": "Pots and herbs",
                    "detail_note": "Drip line, flat, every second day",
                },
            )
        }
        hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id))
        )
        flow_alert = FlowAlertSnapshot(
            rule_id="flow-1",
            zone_name="Pots Dawn Micro",
            alert_kind="low_flow",
            alert_at="2026-05-10T05:00:00+10:00",
            alert_summary="Low flow in Pots Dawn Micro",
            status="calibration_required",
            reason="needs calibration",
            recommended_action="calibrate in Rachio",
            baseline_before_lpm=None,
            baseline_after_lpm=None,
            baseline_delta_percent=None,
            calibration_at=None,
            review_state="pending_review",
            summary="calibration required",
        )

        items = build_zone_overview_items(hass, (schedule,), (flow_alert,))

        self.assertEqual(items[0]["zone_name"], "Pots - Dawn Micro")
        self.assertEqual(items[0]["image_path"], "/rachio_supervisor/zone-placeholder.svg")
        self.assertEqual(items[0]["image_source"], "placeholder")
        self.assertEqual(
            items[0]["suggested_image_path"],
            "/local/rachio-supervisor/zones/dawn-micro-pots.jpg",
        )
        self.assertEqual(
            items[0]["fallback_image_path"],
            "/rachio_supervisor/zone-placeholder.svg",
        )
        self.assertFalse(items[0]["rachio_image_available"])
        self.assertEqual(items[0]["photo_import_status"], "disabled")
        self.assertEqual(items[0]["next_run"], "Tue 06:00")
        self.assertEqual(items[0]["watering_days"], ["M", "W", "F"])
        self.assertEqual(items[0]["rain_skip_state"], "none")
        self.assertEqual(items[0]["flow_alert_state"], "calibration_required")
        self.assertEqual(items[0]["supervisor_badge"], "flow")
        self.assertEqual(items[0]["plant_note"], "Pots and herbs")
        self.assertEqual(items[0]["detail_note"], "Drip line, flat, every second day")
        self.assertEqual(items[0]["water_badge"], "watered")

    def test_zone_overview_ignores_stale_imported_cache_when_import_disabled(self) -> None:
        schedule = ScheduleSnapshot(
            rule_id="rule-1",
            name="Pots - Dawn Micro",
            status="completed_recently",
            reason="ran",
            catch_up_candidate="not_needed",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id="switch.schedule_pots",
            zone_entity_id="switch.zone_pots",
            controller_zone_id="zone-1",
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="none",
            runtime_minutes=3,
            last_run_at="2026-05-10T06:00:00+10:00",
            last_skip_at=None,
            summary="ran",
            threshold_mm=None,
            observed_mm=None,
            photo_import_status="disabled",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = (
                root
                / "www"
                / "rachio-supervisor"
                / "imported-zones"
                / "zone-1.jpg"
            )
            image.parent.mkdir(parents=True)
            image.write_bytes(b"stale cache")
            hass = SimpleNamespace(
                states=SimpleNamespace(get=lambda entity_id: None),
                config=SimpleNamespace(path=lambda *parts: str(root.joinpath(*parts))),
            )

            items = build_zone_overview_items(hass, (schedule,))

        self.assertEqual(items[0]["image_path"], "/rachio_supervisor/zone-placeholder.svg")
        self.assertEqual(items[0]["image_source"], "placeholder")
        self.assertEqual(items[0]["photo_import_status"], "disabled")

    def test_zone_overview_uses_existing_local_zone_image(self) -> None:
        schedule = ScheduleSnapshot(
            rule_id="rule-1",
            name="Pots - Dawn Micro",
            status="completed_recently",
            reason="ran",
            catch_up_candidate="not_needed",
            policy_mode="observe_only",
            policy_basis="default",
            schedule_entity_id="switch.schedule_pots",
            zone_entity_id="switch.zone_pots",
            controller_zone_id="zone-1",
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="none",
            review_state="none",
            runtime_minutes=3,
            last_run_at="2026-05-10T06:00:00+10:00",
            last_skip_at=None,
            summary="ran",
            threshold_mm=None,
            observed_mm=None,
            imported_image_path="/local/rachio-supervisor/imported-zones/zone-1.jpg",
            rachio_image_available=True,
            photo_import_status="cached",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "www" / "rachio-supervisor" / "zones" / "dawn-micro-pots.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"fake jpg")
            hass = SimpleNamespace(
                states=SimpleNamespace(get=lambda entity_id: None),
                config=SimpleNamespace(path=lambda *parts: str(root.joinpath(*parts))),
            )

            items = build_zone_overview_items(hass, (schedule,))

        self.assertEqual(
            items[0]["image_path"],
            "/local/rachio-supervisor/zones/dawn-micro-pots.jpg",
        )
        self.assertEqual(items[0]["image_source"], "local_override")
        self.assertEqual(
            items[0]["fallback_image_path"],
            "/rachio_supervisor/zone-placeholder.svg",
        )

    def test_zone_overview_preserves_photo_metadata_after_moisture_mapping(self) -> None:
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
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="pending_moisture_eval",
            review_state="pending",
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
            imported_image_path="/local/rachio-supervisor/imported-zones/zone-1.jpg",
            rachio_image_available=True,
            photo_import_status="cached",
        )
        moisture_state = SimpleNamespace(
            state="13",
            attributes={},
            last_updated=datetime.fromisoformat("2026-05-10T02:12:51+00:00"),
        )
        state_map = {"sensor.pots_moisture": moisture_state}
        hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id))
        )

        mapped = apply_moisture_mapping(
            hass,
            (schedule,),
            {"switch.schedule_pots": "sensor.pots_moisture"},
            set(),
            {"switch.schedule_pots"},
            {},
        )
        items = build_zone_overview_items(hass, mapped)

        self.assertEqual(
            items[0]["image_path"],
            "/local/rachio-supervisor/imported-zones/zone-1.jpg",
        )
        self.assertEqual(items[0]["image_source"], "rachio_import")
        self.assertEqual(items[0]["photo_import_status"], "cached")
        self.assertEqual(items[0]["moisture_band"], "dry")
        self.assertEqual(items[0]["moisture_value"], "13")
        self.assertEqual(items[0]["moisture_observed_value"], "13")
        self.assertEqual(items[0]["moisture_freshness"], "fresh")
        self.assertIn("moisture_quality_note", items[0])

    def test_zone_overview_card_static_contract(self) -> None:
        card_path = (
            REPO_ROOT
            / "custom_components"
            / "rachio_supervisor"
            / "www"
            / "rachio-supervisor-zone-grid-card.js"
        )
        source = card_path.read_text()

        self.assertIn(
            'customElements.define("rachio-supervisor-zone-grid-card"',
            source,
        )
        self.assertIn('"quick_run_zone"', source)
        self.assertIn("window.customCards", source)
        self.assertIn("data-quick-run-index", source)
        self.assertIn("hass-notification", source)
        self.assertIn("_pendingQuickRunIndex", source)
        self.assertIn("_timeLabel", source)
        self.assertIn("detail-row", source)
        self.assertIn("health_entity", source)
        self.assertIn("flow_entity", source)
        self.assertIn("calibration_entities", source)
        self.assertIn("moisture_entity_id", source)
        self.assertIn("moistureEntity", source)
        self.assertIn("data-apply-calibration-index", source)
        self.assertIn('"number", "set_value"', source)
        self.assertIn("currentOffset: this._parseNumber(soilState.state)", source)
        self.assertIn("_suggestedCalibrationValue", source)
        self.assertIn("_supervisorTemplate", source)
        self.assertIn("_supervisorPills", source)
        self.assertIn("Supervisor needs review", source)
        self.assertIn("Supervisor not ready", source)
        self.assertIn("Data warnings", source)
        self.assertIn("_photoBadge", source)
        self.assertIn("_photoErrorLabel", source)
        self.assertIn("image too large", source)
        self.assertIn("No photo", source)
        self.assertIn("show_disabled_photo_status", source)
        self.assertIn("_moistureLabel", source)
        self.assertIn("_moistureTitle", source)
        self.assertIn("Last valid moisture", source)
        self.assertTrue(
            (
                REPO_ROOT
                / "custom_components"
                / "rachio_supervisor"
                / "www"
                / "zone-placeholder.svg"
            ).exists()
        )

    def test_apply_moisture_mapping_marks_auto_write_eligibility(self) -> None:
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
            moisture_entity_id=None,
            moisture_value=None,
            moisture_band="unmapped",
            moisture_status="pending",
            moisture_write_back_ready="ready",
            recommended_action="pending_moisture_eval",
            review_state="pending",
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
            imported_image_path="/local/rachio-supervisor/imported-zones/zone-1.jpg",
            rachio_image_available=True,
            photo_import_status="cached",
            photo_import_reason="imageUrl_missing",
        )
        state = SimpleNamespace(
            state="13",
            attributes={},
            last_updated=datetime.fromisoformat("2026-05-10T02:12:51+00:00"),
        )
        hass = SimpleNamespace(
            states=SimpleNamespace(
                get=lambda entity_id: state if entity_id == "sensor.pots_moisture" else None
            )
        )

        mapped = apply_moisture_mapping(
            hass,
            (schedule,),
            {"switch.schedule_pots": "sensor.pots_moisture"},
            set(),
            {"switch.schedule_pots"},
            {},
        )[0]

        self.assertEqual(mapped.recommended_action, "write_moisture_now")
        self.assertTrue(mapped.auto_moisture_write_enabled)
        self.assertEqual(mapped.auto_moisture_write_status, "eligible")
        self.assertEqual(mapped.write_value, "13")
        self.assertEqual(mapped.write_summary, "Sensor 13% -> Rachio zone moisture")
        self.assertEqual(
            mapped.imported_image_path,
            "/local/rachio-supervisor/imported-zones/zone-1.jpg",
        )
        self.assertTrue(mapped.rachio_image_available)
        self.assertEqual(mapped.photo_import_status, "cached")
        self.assertEqual(mapped.photo_import_reason, "imageUrl_missing")
        self.assertEqual(mapped.moisture_observed_value, "13")
        self.assertEqual(mapped.moisture_freshness, "fresh")

    def test_recent_cached_moisture_can_recommend_manual_write_but_blocks_auto(self) -> None:
        current = datetime.fromisoformat("2026-05-10T12:00:00+00:00")
        cache = {
            "sensor.pots_moisture": MoistureEvidenceCacheEntry(
                observed_value="13",
                observed_at="2026-05-10T00:00:00+00:00",
            )
        }
        state_map = {
            "sensor.pots_moisture": SimpleNamespace(
                entity_id="sensor.pots_moisture",
                state="unknown",
                attributes={},
                last_updated=current,
            )
        }

        mapped = apply_moisture_mapping(
            self._hass_with_states(state_map),
            (self._moisture_schedule(),),
            {"switch.schedule_pots": "sensor.pots_moisture"},
            set(),
            {"switch.schedule_pots"},
            {},
            True,
            cache,
            current,
        )[0]

        self.assertEqual(mapped.recommended_action, "write_moisture_now")
        self.assertEqual(mapped.write_value, "13")
        self.assertEqual(mapped.moisture_freshness, "recent")
        self.assertEqual(mapped.auto_moisture_write_status, "blocked")

    def test_stale_and_expired_moisture_block_recommendations(self) -> None:
        current = datetime.fromisoformat("2026-05-10T12:00:00+00:00")
        for observed_at, expected in (
            ("2026-05-09T00:00:00+00:00", "stale"),
            ("2026-05-07T04:00:00+00:00", "expired"),
        ):
            with self.subTest(expected=expected):
                mapped = apply_moisture_mapping(
                    self._hass_with_states({}),
                    (self._moisture_schedule(),),
                    {"switch.schedule_pots": "sensor.pots_moisture"},
                    set(),
                    {"switch.schedule_pots"},
                    {},
                    True,
                    {
                        "sensor.pots_moisture": MoistureEvidenceCacheEntry(
                            observed_value="13",
                            observed_at=observed_at,
                        )
                    },
                    current,
                )[0]

                self.assertEqual(mapped.moisture_freshness, expected)
                self.assertEqual(mapped.recommended_action, "repair_moisture_sensor")
                self.assertIsNone(mapped.write_value)

    def test_boundary_moisture_blocks_recommendation_and_auto_write(self) -> None:
        cache: dict[str, MoistureEvidenceCacheEntry] = {}
        schedule = self._moisture_schedule()
        first_state = SimpleNamespace(
            entity_id="sensor.pots_moisture",
            state="0",
            attributes={},
            last_updated=datetime.fromisoformat("2026-05-10T06:00:00+00:00"),
        )
        second_state = SimpleNamespace(
            entity_id="sensor.pots_moisture",
            state="0",
            attributes={},
            last_updated=datetime.fromisoformat("2026-05-10T06:30:00+00:00"),
        )

        apply_moisture_mapping(
            self._hass_with_states({"sensor.pots_moisture": first_state}),
            (schedule,),
            {"switch.schedule_pots": "sensor.pots_moisture"},
            set(),
            {"switch.schedule_pots"},
            {},
            True,
            cache,
            datetime.fromisoformat("2026-05-10T06:05:00+00:00"),
        )
        mapped = apply_moisture_mapping(
            self._hass_with_states({"sensor.pots_moisture": second_state}),
            (schedule,),
            {"switch.schedule_pots": "sensor.pots_moisture"},
            set(),
            {"switch.schedule_pots"},
            {},
            True,
            cache,
            datetime.fromisoformat("2026-05-10T06:35:00+00:00"),
        )[0]

        self.assertEqual(mapped.recommended_action, "calibrate_moisture_sensor")
        self.assertEqual(mapped.auto_moisture_write_status, "watching")
        self.assertIn("boundary_value_needs_calibration", mapped.moisture_quality_flags)

    def test_auto_moisture_write_records_written_then_cooldown(self) -> None:
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
            moisture_value="13",
            moisture_band="dry",
            moisture_status="ok",
            moisture_write_back_ready="ready",
            recommended_action="write_moisture_now",
            review_state="pending_review",
            runtime_minutes=3,
            last_run_at=None,
            last_skip_at=None,
            summary="none",
            threshold_mm=None,
            observed_mm=None,
            write_value="13",
            write_summary="Sensor 13% -> Rachio zone moisture",
            auto_moisture_write_enabled=True,
            auto_moisture_write_status="eligible",
            moisture_observed_value="13",
            moisture_observed_at="2026-05-10T02:12:51+00:00",
            moisture_age_label="4h",
            moisture_freshness="fresh",
            moisture_confidence="low",
        )
        calls: list[tuple[str, float]] = []

        class _Client:
            def __init__(self, _token: str) -> None:
                pass

            def set_zone_moisture_percent(self, zone_id: str, value: float) -> None:
                calls.append((zone_id, value))

        async def _executor(func, *args):
            return func(*args)

        coordinator = object.__new__(RachioSupervisorCoordinator)
        coordinator.hass = SimpleNamespace(async_add_executor_job=_executor)
        coordinator._last_moisture_write_status = "none"
        coordinator._last_moisture_write_at = None
        coordinator._last_moisture_write_schedule = None
        coordinator._last_moisture_write_value = None
        coordinator._auto_moisture_write_lockouts = {}
        coordinator._moisture_write_status_by_rule = {}

        with patch.object(coordinator_module, "RachioClient", _Client):
            asyncio.run(
                coordinator._async_execute_auto_moisture_writes(
                    linked_entry=SimpleNamespace(),
                    api_key="token",
                    schedules=(schedule,),
                    current=datetime.fromisoformat("2026-05-10T08:00:00"),
                )
            )
            asyncio.run(
                coordinator._async_execute_auto_moisture_writes(
                    linked_entry=SimpleNamespace(),
                    api_key="token",
                    schedules=(schedule,),
                    current=datetime.fromisoformat("2026-05-10T09:00:00"),
                )
            )

        self.assertEqual(calls, [("zone-1", 13.0)])
        self.assertEqual(coordinator._last_moisture_write_status, "auto_skipped_cooldown")
        self.assertEqual(
            coordinator._moisture_write_status_by_rule["rule-1"],
            "auto_skipped_cooldown",
        )


class ConfigFlowBehaviorTests(unittest.TestCase):
    def _hass(self) -> SimpleNamespace:
        return SimpleNamespace(
            states=SimpleNamespace(get=lambda _entity_id: None),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )

    def test_discovers_likely_moisture_sensors_for_config_defaults(self) -> None:
        states = [
            SimpleNamespace(
                entity_id="sensor.pots_soil_moisture",
                attributes={
                    "friendly_name": "Pots soil moisture",
                    "unit_of_measurement": "%",
                },
            ),
            SimpleNamespace(
                entity_id="sensor.pots_soil_temperature",
                attributes={"friendly_name": "Pots soil temperature"},
            ),
            SimpleNamespace(
                entity_id="sensor.pots_battery",
                attributes={"friendly_name": "Pots battery"},
            ),
        ]
        hass = SimpleNamespace(states=SimpleNamespace(async_all=lambda domain: states))

        discovered = config_flow.discover_moisture_sensor_entities(hass)

        self.assertEqual(discovered, ["sensor.pots_soil_moisture"])

    def test_discovers_zone_count_for_config_defaults(self) -> None:
        linked = LinkedRachioEntities(
            connectivity_entity_id=None,
            rain_entity_id=None,
            rain_delay_entity_id=None,
            standby_entity_id=None,
            zone_switches=("switch.zone_1", "switch.zone_2"),
            schedule_switches=(),
            zone_entities=(
                ZoneEntityRef("switch.zone_1", "Zone 1", None),
                ZoneEntityRef("switch.zone_2", "Zone 2", None),
            ),
            schedule_entities=(),
            all_entities=("switch.zone_1", "switch.zone_2"),
        )

        with patch.object(config_flow, "discover_linked_entities", return_value=linked):
            count = config_flow.discover_zone_count(self._hass(), "entry-1")

        self.assertEqual(count, 2)

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
            return_value=[("entry-1", "Demo Rachio")],
        ):
            result = asyncio.run(flow.async_step_user())

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")

    def test_config_flow_skips_moisture_map_when_no_sensors_selected(self) -> None:
        flow = config_flow.RachioSupervisorConfigFlow()
        flow.hass = self._hass()
        flow._basic_input = {
            "site_name": "Demo Site",
            "rachio_config_entry_id": "entry-1",
            "moisture_sensor_entities": [],
        }
        flow._policy_input = {
            "auto_catch_up_schedule_entities": [],
            "auto_missed_run_schedule_entities": [],
        }

        result = asyncio.run(flow.async_step_moisture_map())

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Demo Site")
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
            "site_name": "Demo Site",
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
        schema_markers = [marker.value for marker in prompt["data_schema"].value.keys()]
        self.assertIn(config_flow.MOISTURE_SCHEDULE_CONTEXT_FIELD, schema_markers)
        self.assertIn(config_flow.MOISTURE_SENSOR_FIELD, schema_markers)

        result = asyncio.run(
            flow.async_step_moisture_map(
                {
                    config_flow.MOISTURE_SCHEDULE_CONTEXT_FIELD: "Pots - Dawn Micro",
                    config_flow.MOISTURE_SENSOR_FIELD: "sensor.moisture_pots",
                }
            )
        )
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"]["schedule_moisture_map"],
            {"switch.schedule_pots": "sensor.moisture_pots"},
        )

    def test_options_flow_maps_schedule_with_stable_field_key(self) -> None:
        state_map = {
            "sensor.moisture_boxwoods": SimpleNamespace(
                attributes={"friendly_name": "Boxwoods Liriopes Moisture"}
            )
        }
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id)),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )
        flow._basic_input = {"moisture_sensor_entities": ["sensor.moisture_boxwoods"]}
        flow._policy_input = {}
        flow._schedule_options = [("switch.schedule_boxwoods", "Boxwood + Liriope Schedule")]

        result = asyncio.run(
            flow.async_step_moisture_map(
                {config_flow.MOISTURE_SENSOR_FIELD: "sensor.moisture_boxwoods"}
            )
        )

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"]["schedule_moisture_map"],
            {"switch.schedule_boxwoods": "sensor.moisture_boxwoods"},
        )

    def test_options_flow_advances_unmapped_schedule(self) -> None:
        state_map = {
            "sensor.moisture_boxwoods": SimpleNamespace(
                attributes={"friendly_name": "Boxwoods Liriopes Moisture"}
            )
        }
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id)),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )
        flow._basic_input = {"moisture_sensor_entities": ["sensor.moisture_boxwoods"]}
        flow._policy_input = {}
        flow._schedule_options = [
            ("switch.schedule_boxwoods", "Boxwood + Liriope"),
            ("switch.schedule_driveway", "Driveway Hedge"),
        ]

        result = asyncio.run(
            flow.async_step_moisture_map(
                {
                    config_flow.MOISTURE_SCHEDULE_CONTEXT_FIELD: "Boxwood + Liriope",
                    config_flow.MOISTURE_SENSOR_FIELD: config_flow.UNMAPPED_SENTINEL,
                }
            )
        )

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "moisture_map")
        self.assertEqual(flow._mapping_index, 1)
        self.assertEqual(flow._moisture_mapping, {})
        self.assertEqual(
            result["description_placeholders"]["schedule_name"],
            "Driveway Hedge",
        )

    def test_options_flow_maps_multiple_schedules_with_stable_field_key(self) -> None:
        state_map = {
            "sensor.moisture_boxwoods": SimpleNamespace(
                attributes={"friendly_name": "Boxwoods Liriopes Moisture"}
            ),
            "sensor.moisture_driveway": SimpleNamespace(
                attributes={"friendly_name": "Driveway - South/Hedge Moisture"}
            ),
        }
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id)),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )
        flow._basic_input = {
            "moisture_sensor_entities": [
                "sensor.moisture_boxwoods",
                "sensor.moisture_driveway",
            ]
        }
        flow._policy_input = {}
        flow._schedule_options = [
            ("switch.schedule_boxwoods", "Boxwood + Liriope"),
            ("switch.schedule_driveway", "Driveway Hedge"),
        ]

        first = asyncio.run(
            flow.async_step_moisture_map(
                {config_flow.MOISTURE_SENSOR_FIELD: "sensor.moisture_boxwoods"}
            )
        )
        self.assertEqual(first["type"], "form")
        self.assertEqual(
            first["description_placeholders"]["schedule_name"],
            "Driveway Hedge",
        )

        result = asyncio.run(
            flow.async_step_moisture_map(
                {config_flow.MOISTURE_SENSOR_FIELD: "sensor.moisture_driveway"}
            )
        )

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"]["schedule_moisture_map"],
            {
                "switch.schedule_boxwoods": "sensor.moisture_boxwoods",
                "switch.schedule_driveway": "sensor.moisture_driveway",
            },
        )

    def test_options_flow_accepts_label_submission_with_extra_hidden_fields(self) -> None:
        state_map = {
            "sensor.moisture_boxwoods": SimpleNamespace(
                attributes={"friendly_name": "Boxwoods Liriopes Moisture"}
            )
        }
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = SimpleNamespace(
            states=SimpleNamespace(get=lambda entity_id: state_map.get(entity_id)),
            config_entries=SimpleNamespace(async_entries=lambda _domain=None: []),
        )
        flow._basic_input = {"moisture_sensor_entities": ["sensor.moisture_boxwoods"]}
        flow._policy_input = {}
        flow._schedule_options = [("switch.schedule_boxwoods", "Boxwood + Liriope Schedule")]

        result = asyncio.run(
            flow.async_step_moisture_map(
                {
                    "some_hidden_key": "Boxwoods Liriopes Moisture",
                    "other_hidden_key": "ignored",
                }
            )
        )

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"]["schedule_moisture_map"],
            {"switch.schedule_boxwoods": "sensor.moisture_boxwoods"},
        )

    def test_options_flow_skips_mapping_when_no_sensors_selected(self) -> None:
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()
        flow._basic_input = {"moisture_sensor_entities": []}
        flow._policy_input = {"auto_catch_up_schedule_entities": []}

        result = asyncio.run(flow.async_step_moisture_map())

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["schedule_moisture_map"], {})

    def test_options_flow_uses_private_entry_storage(self) -> None:
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)

        self.assertIs(flow._entry, entry)
        self.assertIsNone(flow.config_entry)

    def test_options_flow_aborts_without_linked_rachio_entries(self) -> None:
        entry = SimpleNamespace(data={"site_name": "Demo Site"}, options={})
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()

        with patch.object(config_flow, "rachio_entry_options", return_value=[]):
            result = asyncio.run(flow.async_step_init())

        self.assertEqual(result["type"], "abort")
        self.assertEqual(result["reason"], "no_rachio_entries")

    def test_options_flow_recovers_when_saved_linked_entry_is_missing(self) -> None:
        entry = SimpleNamespace(
            data={"site_name": "Demo Site", "rachio_config_entry_id": "missing-entry"},
            options={},
        )
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()

        with patch.object(
            config_flow,
            "rachio_entry_options",
            return_value=[("entry-1", "Demo Rachio")],
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

    def test_policy_schema_includes_auto_moisture_write_opt_in(self) -> None:
        schema = config_flow._policy_schema(
            [("switch.schedule_pots", "Pots - Dawn Micro")],
            {"auto_moisture_write_schedule_entities": ["switch.schedule_pots"]},
        )
        marker = next(
            marker
            for marker in schema.value
            if getattr(marker, "value", None) == "auto_moisture_write_schedule_entities"
        )

        self.assertEqual(marker.default, ["switch.schedule_pots"])

    def test_policy_schema_drops_stale_saved_schedule_defaults(self) -> None:
        schema = config_flow._policy_schema(
            [("switch.schedule_pots", "Pots - Dawn Micro")],
            {
                "auto_catch_up_schedule_entities": [
                    "switch.schedule_pots",
                    "switch.old_synthetic_schedule",
                ],
                "auto_missed_run_schedule_entities": ["switch.old_synthetic_schedule"],
                "auto_moisture_write_schedule_entities": ["switch.old_synthetic_schedule"],
            },
        )

        defaults = {
            getattr(marker, "value", None): marker.default
            for marker in schema.value
        }
        self.assertEqual(
            defaults["auto_catch_up_schedule_entities"],
            ["switch.schedule_pots"],
        )
        self.assertEqual(defaults["auto_missed_run_schedule_entities"], [])
        self.assertEqual(defaults["auto_moisture_write_schedule_entities"], [])

    def test_options_flow_uses_unmapped_default_for_stale_moisture_mapping(self) -> None:
        entry = SimpleNamespace(
            data={"site_name": "Demo Site"},
            options={
                "moisture_sensor_entities": ["sensor.moisture_boxwoods"],
                "schedule_moisture_map": {
                    "switch.schedule_boxwoods": "sensor.old_moisture"
                },
            },
        )
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()
        flow._schedule_options = [("switch.schedule_boxwoods", "Boxwood + Liriope")]

        result = asyncio.run(flow.async_step_moisture_map())

        marker = next(
            marker
            for marker in result["data_schema"].value
            if getattr(marker, "value", None) == "moisture_sensor_entity"
        )
        self.assertEqual(marker.default, config_flow.UNMAPPED_SENTINEL)

    def test_flow_schema_includes_optional_rachio_photo_import(self) -> None:
        schema = config_flow._flow_schema(
            [("entry-1", "Demo Rachio")],
            {"import_rachio_zone_photos": True},
        )
        marker = next(
            marker
            for marker in schema.value
            if getattr(marker, "value", None) == "import_rachio_zone_photos"
        )

        self.assertTrue(marker.default)

    def test_flow_schema_includes_weather_underground_station_override(self) -> None:
        schema = config_flow._flow_schema(
            [("entry-1", "Demo Rachio")],
            {
                "rain_source_mode": "weather_underground_pws",
                "weather_underground_station_id": "KCAEXAMP1",
            },
        )
        markers = {getattr(marker, "value", None): marker for marker in schema.value}

        self.assertEqual(
            markers["rain_source_mode"].default,
            "weather_underground_pws",
        )
        self.assertEqual(
            markers["weather_underground_station_id"].default,
            "KCAEXAMP1",
        )
        self.assertIn("weather_underground_api_key", markers)

    def test_weather_underground_mode_requires_station_and_key(self) -> None:
        flow = config_flow.RachioSupervisorConfigFlow()
        flow.hass = self._hass()
        user_input = {
            "site_name": "Demo Site",
            "rachio_config_entry_id": "entry-1",
            "rain_source_mode": "weather_underground_pws",
            "weather_underground_station_id": "",
            "weather_underground_api_key": "",
            "moisture_sensor_entities": [],
        }

        with patch.object(
            config_flow,
            "rachio_entry_options",
            return_value=[("entry-1", "Demo Rachio")],
        ):
            result = asyncio.run(flow.async_step_user(user_input))

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(
            result["errors"]["weather_underground_station_id"],
            "required",
        )
        self.assertEqual(
            result["errors"]["weather_underground_api_key"],
            "required",
        )

    def test_options_flow_preserves_saved_weather_underground_api_key(self) -> None:
        entry = SimpleNamespace(
            data={
                "site_name": "Demo Site",
                "rachio_config_entry_id": "entry-1",
                "weather_underground_api_key": "saved-key",
            },
            options={},
        )
        flow = config_flow.RachioSupervisorOptionsFlow(entry)
        flow.hass = self._hass()
        flow._schedule_options = []
        user_input = {
            "site_name": "Demo Site",
            "rachio_config_entry_id": "entry-1",
            "rain_source_mode": "weather_underground_pws",
            "weather_underground_station_id": "kcaexamp1",
            "weather_underground_api_key": "",
            "moisture_sensor_entities": [],
        }

        with patch.object(
            config_flow,
            "rachio_entry_options",
            return_value=[("entry-1", "Demo Rachio")],
        ):
            first = asyncio.run(flow.async_step_init(user_input))
        self.assertEqual(first["type"], "form")
        self.assertEqual(first["step_id"], "policy")

        result = asyncio.run(
            flow.async_step_policy(
                {
                    "auto_catch_up_schedule_entities": [],
                    "auto_missed_run_schedule_entities": [],
                    "auto_moisture_write_schedule_entities": [],
                }
            )
        )

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(
            result["data"]["weather_underground_station_id"],
            "KCAEXAMP1",
        )
        self.assertEqual(
            result["data"]["weather_underground_api_key"],
            "saved-key",
        )


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
            site_name="Demo Site",
            linked_entry_title="Demo Rachio",
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
            rain_actuals_reason="Observed rainfall total resolved from a numeric Home Assistant entity.",
            rain_actuals_window="24h",
            rain_actuals_confidence="high",
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
            catch_up_evidence_label="No catch-up needed",
            catch_up_action_label="No action",
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
            zone_overview_items=(
                {
                    "zone_name": "Pots - Dawn Micro",
                    "image_path": "/local/rachio-supervisor/zones/dawn-micro-pots.jpg",
                    "water_badge": "watch",
                    "supervisor_badge": "ok",
                },
            ),
            rain_source_candidates=(
                {
                    "entity_id": "sensor.rain_24h",
                    "status": "ok",
                    "window": "24h",
                    "confidence": "high",
                },
            ),
            rachio_weather_probe={"used_for_actual_rain": False, "hints": []},
            weather_outlook={
                "status": "forecast_unavailable",
                "used_for_actual_rain": False,
            },
            discovered_entities={"entity_count": 10},
            schedule_snapshots=(schedule,),
        )

    def test_diagnostics_payload_contains_snapshot_and_notes(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(data=snapshot)
        hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        entry = SimpleNamespace(
            entry_id="entry-1",
            title="Demo Site",
            data={"site_name": "Demo Site"},
            options={"observe_first": True},
        )

        payload = asyncio.run(diagnostics.async_get_config_entry_diagnostics(hass, entry))

        self.assertEqual(payload["domain"], DOMAIN)
        self.assertEqual(payload["snapshot"]["health"], "healthy")
        self.assertIn("Automatic irrigation behavior remains intentionally narrow and opt-in.", payload["notes"])

    def test_diagnostics_redacts_weather_underground_api_key(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(data=snapshot)
        hass = SimpleNamespace(data={DOMAIN: {"entry-1": coordinator}})
        entry = SimpleNamespace(
            entry_id="entry-1",
            title="Demo Site",
            data={"site_name": "Demo Site"},
            options={"weather_underground_api_key": "secret-key"},
        )

        payload = asyncio.run(diagnostics.async_get_config_entry_diagnostics(hass, entry))

        self.assertEqual(
            payload["entry_options"]["weather_underground_api_key"],
            "**REDACTED**",
        )

    def test_site_sensor_sets_explicit_name_and_attributes(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
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

    def test_zone_overview_sensor_exposes_photo_import_diagnostics(self) -> None:
        snapshot = replace(
            self._snapshot(),
            zone_overview_items=(
                {"zone_name": "A", "photo_import_status": "cached"},
                {"zone_name": "B", "photo_import_status": "imported"},
                {"zone_name": "C", "photo_import_status": "missing"},
                {"zone_name": "D", "photo_import_status": "rejected"},
                {"zone_name": "E", "photo_import_status": "failed"},
                {"zone_name": "F", "photo_import_status": "disabled"},
                {"zone_name": "G", "photo_import_status": "cached"},
            ),
        )
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
            data=snapshot,
            _cached_evidence=None,
        )
        description = next(
            item for item in sensor_module.DESCRIPTIONS if item.key == "zone_overview"
        )

        entity = sensor_module.RachioSupervisorSensor(coordinator, description)
        attrs = entity.extra_state_attributes

        self.assertEqual(
            attrs["photo_import_counts"],
            {
                "disabled": 1,
                "cached": 2,
                "imported": 1,
                "missing": 1,
                "rejected": 1,
                "failed": 1,
            },
        )
        self.assertEqual(
            attrs["photo_import_summary"],
            "1 disabled, 2 cached, 1 imported, 1 missing, 1 rejected, 1 failed",
        )
        self.assertEqual(len(attrs["zones"]), 7)

    def test_health_sensor_exposes_runtime_and_data_completeness(self) -> None:
        snapshot = self._snapshot()
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
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

    def test_heat_assist_sensor_exposes_read_only_weather_outlook(self) -> None:
        snapshot = replace(
            self._snapshot(),
            weather_outlook={
                "status": "forecast_available",
                "summary": "Now: Showers; Next: Mostly Sunny",
                "heat_assist_state": "weather_outlook_only",
                "action_label": "No heat top-up automation is implemented in v1.",
                "source": "rachio_public_forecast",
                "used_for_actual_rain": False,
            },
        )
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
            data=snapshot,
            _cached_evidence=None,
        )
        description = next(
            item for item in sensor_module.DESCRIPTIONS if item.key == "heat_assist"
        )

        entity = sensor_module.RachioSupervisorSensor(coordinator, description)

        self.assertEqual(entity.native_value, "Now: Showers; Next: Mostly Sunny")
        self.assertEqual(entity.extra_state_attributes["status"], "forecast_available")
        self.assertFalse(entity.extra_state_attributes["used_for_actual_rain"])

    def test_catch_up_evidence_sensor_uses_human_evidence_state_and_status_attr(self) -> None:
        snapshot = replace(
            self._snapshot(),
            catch_up_evidence_status="deferred",
            catch_up_evidence_reason="review_recommended",
            catch_up_schedule_name="Front Lower Mixed Bed",
            catch_up_runtime_minutes=45,
            catch_up_evidence_label=(
                "Front Lower Mixed Bed: Rachio skip on 2026-05-06; 0.17 mm; threshold 6.35 mm"
            ),
            catch_up_action_label=(
                "Review catch-up for Front Lower Mixed Bed; automatic run is not enabled."
            ),
        )
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
            data=snapshot,
            _cached_evidence=None,
        )
        description = next(
            item for item in sensor_module.DESCRIPTIONS if item.key == "catch_up_evidence"
        )

        entity = sensor_module.RachioSupervisorSensor(coordinator, description)

        self.assertIn("0.17 mm", entity.native_value)
        self.assertEqual(entity.extra_state_attributes["status"], "deferred")
        self.assertIn("Review catch-up", entity.extra_state_attributes["action_label"])

    def test_last_run_sensor_exposes_compact_decision_fields(self) -> None:
        snapshot = self._snapshot()
        snapshot = replace(
            snapshot,
            last_run_summary="Pots - Dawn Micro ran for 3 minutes.",
        )
        coordinator = SimpleNamespace(
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
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
            entry=SimpleNamespace(entry_id="entry-1", title="Demo Site"),
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
