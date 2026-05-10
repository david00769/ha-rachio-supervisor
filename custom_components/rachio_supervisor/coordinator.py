"""Coordinator scaffold for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import urllib.parse

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    CONF_AUTO_CATCH_UP_SCHEDULES,
    CONF_AUTO_MOISTURE_WRITE_SCHEDULES,
    CONF_AUTO_MISSED_RUN_SCHEDULES,
    CONF_CLOUDHOOK_URL,
    CONF_ENABLE_PERSISTENT_NOTIFICATIONS,
    CONF_HEALTH_RECONCILE_HOUR,
    CONF_HEALTH_RECONCILE_MINUTE,
    CONF_IMPORT_RACHIO_ZONE_PHOTOS,
    CONF_MOISTURE_SENSOR_ENTITIES,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_SAFE_WINDOW_END_HOUR,
    CONF_SCHEDULE_MOISTURE_MAP,
    CONF_SITE_NAME,
    CONF_WEBHOOK_ID,
    CONF_ZONE_COUNT,
    DEFAULT_ENABLE_PERSISTENT_NOTIFICATIONS,
    DEFAULT_HEALTH_RECONCILE_HOUR,
    DEFAULT_HEALTH_RECONCILE_MINUTE,
    DEFAULT_IMPORT_RACHIO_ZONE_PHOTOS,
    DEFAULT_SAFE_WINDOW_END_HOUR,
    DOMAIN,
    WEBHOOK_CONST_ID,
)
from .discovery import (
    LinkedRachioEntities,
    ScheduleEntityRef,
    ZoneEntityRef,
    discover_linked_entities,
)
from .photo_import import imported_zone_photo_paths, import_rachio_zone_photo
from .rachio_api import RachioClient, RachioClientError

EVENT_LOOKBACK_HOURS = 168
EXPECTED_EVENT_FRESHNESS_HOURS = 36
DEGRADED_FAST_WINDOW_HOURS = 2
AUTO_MOISTURE_WRITE_COOLDOWN_HOURS = 24
ZONE_PLACEHOLDER_PATH = "/rachio_supervisor/zone-placeholder.svg"
WORD_RE = re.compile(r"[a-z0-9]+")

RAIN_MM_RE = re.compile(r"observed ([0-9.]+) mm(?: and predicted ([0-9.]+) mm)?")
THRESHOLD_MM_RE = re.compile(r"threshold of ([0-9.]+) mm")
FLOW_ALERT_RE = re.compile(r"\b(?P<kind>low|high)[ -]?flow\b", re.IGNORECASE)
FLOW_BASELINE_RE = re.compile(
    r"baseline flow rate for (?P<zone>.+?) is now set at (?P<flow>[0-9.]+)\s*lpm",
    re.IGNORECASE,
)
FLOW_ALERT_ZONE_RE = re.compile(
    r"(?:low|high)[ -]?flow(?:[^A-Za-z0-9]+(?:in|for|on))? (?P<zone>.+?)(?: at |\.|$)",
    re.IGNORECASE,
)
FLOW_STABLE_TOLERANCE_RATIO = 0.15
DRY_THRESHOLD = 25.0
WET_THRESHOLD = 60.0
RAIN_HINT_WORDS = ("rain", "rainfall", "precip", "precipitation")
WEATHER_PROBE_HINT_WORDS = (
    "weather",
    "station",
    "source",
    "provider",
    "pws",
    "rain",
    "precip",
)
RAIN_TOTAL_ATTRIBUTE_ALIASES = {
    "rain24h": ("rain_24h", "24h", "high"),
    "rainlast24h": ("rain_last_24h", "24h", "high"),
    "precipitation24h": ("precipitation_24h", "24h", "high"),
    "preciptotal24h": ("precipTotal24h", "24h", "high"),
    "observedprecipitation24h": ("observed_precipitation_24h", "24h", "high"),
    "raintoday": ("rain_today", "today", "medium"),
    "dailyrain": ("daily_rain", "today", "medium"),
    "precipitationtoday": ("precipitation_today", "today", "medium"),
    "preciptoday": ("precip_today", "today", "medium"),
    "preciptotal": ("precipTotal", "today", "medium"),
    "observedprecipitation": ("observed_precipitation", "observed_total", "medium"),
    "observedrain": ("observed_rain", "observed_total", "medium"),
    "rain": ("rain", "observed_total", "medium"),
    "precipitation": ("precipitation", "observed_total", "medium"),
    "rainsince9am": ("rain_since_9am", "since_9am", "medium"),
    "rainfall9am": ("rainfall_9am", "since_9am", "medium"),
    "rainlasthour": ("rain_last_hour", "last_hour", "low"),
}
RAIN_RATE_ATTRIBUTE_ALIASES = {
    "rainrate",
    "preciprate",
    "precipitationrate",
}


@dataclass(frozen=True, slots=True)
class RainActualsResolution:
    """Resolved observed-rain source details."""

    value: str
    unit: str | None
    status: str
    missing_input: str | None
    reason: str | None
    window: str
    confidence: str


@dataclass(slots=True)
class ScheduleSnapshot:
    """Schedule-level status snapshot."""

    rule_id: str
    name: str
    status: str
    reason: str
    catch_up_candidate: str
    policy_mode: str
    policy_basis: str
    schedule_entity_id: str | None
    zone_entity_id: str | None
    controller_zone_id: str | None
    moisture_entity_id: str | None
    moisture_value: str | None
    moisture_band: str
    moisture_status: str
    moisture_write_back_ready: str
    recommended_action: str
    review_state: str
    runtime_minutes: int
    last_run_at: str | None
    last_skip_at: str | None
    summary: str
    threshold_mm: float | None
    observed_mm: float | None
    moisture_last_updated: str | None = None
    rachio_moisture_value: str | None = None
    write_value: str | None = None
    write_summary: str = "No moisture write target."
    auto_moisture_write_enabled: bool = False
    auto_moisture_write_status: str = "off"
    last_moisture_write_status: str | None = None
    imported_image_path: str | None = None
    rachio_image_available: bool = False
    photo_import_status: str = "disabled"
    photo_import_reason: str | None = None


@dataclass(slots=True)
class RachioEvidenceSnapshot:
    """Controller evidence returned from the public Rachio API."""

    controller_name: str
    controller_id: str
    last_event_summary: str
    last_event_at: str | None
    last_run_summary: str
    last_run_at: str | None
    last_skip_summary: str
    last_skip_at: str | None
    observed_rain_24h: str
    observed_rain_status: str
    observed_rain_best_event: dict[str, object] | None
    webhook_count: int
    webhook_health: str
    webhook_url: str | None
    webhook_external_id: str | None
    flow_alert_snapshots: tuple["FlowAlertSnapshot", ...]
    schedule_snapshots: tuple[ScheduleSnapshot, ...]
    weather_source_probe: dict[str, object] | None = None


@dataclass(slots=True)
class FlowAlertSnapshot:
    """Flow-alert review status derived from Rachio event history."""

    rule_id: str
    zone_name: str
    alert_kind: str
    alert_at: str
    alert_summary: str
    status: str
    reason: str
    recommended_action: str
    baseline_before_lpm: float | None
    baseline_after_lpm: float | None
    baseline_delta_percent: float | None
    calibration_at: str | None
    review_state: str
    summary: str


@dataclass(slots=True)
class SupervisorSnapshot:
    """Site-level public snapshot for the first runtime milestone."""

    health: str
    supervisor_mode: str
    supervisor_reason: str
    data_completeness: str
    missing_inputs: tuple[str, ...]
    runtime_integrity: str
    mode: str
    action_posture: str
    site_name: str
    linked_entry_title: str
    linked_entry_state: str
    rachio_config_entry_id: str
    rain_actuals_entity: str
    zone_count: int
    configured_zone_count: int
    active_zone_count: int
    active_schedule_count: int
    connectivity: str
    rain_state: str
    rain_delay_state: str
    standby_state: str
    actual_rain_value: str
    actual_rain_unit: str | None
    rain_actuals_status: str
    rain_actuals_reason: str
    rain_actuals_window: str
    rain_actuals_confidence: str
    controller_name: str
    controller_id: str
    last_event_summary: str
    last_event_at: str | None
    last_run_summary: str
    last_run_at: str | None
    last_skip_summary: str
    last_skip_at: str | None
    observed_rain_24h: str
    observed_rain_status: str
    observed_rain_best_event: dict[str, object] | None
    webhook_count: int
    webhook_health: str
    webhook_url: str | None
    webhook_external_id: str | None
    ready_moisture_write_count: int
    moisture_write_queue: str
    recommended_moisture_write_count: int
    recommended_moisture_write_queue: str
    active_recommendation_count: int
    active_recommendation_queue: str
    acknowledged_recommendation_count: int
    acknowledged_recommendation_queue: str
    catch_up_evidence_status: str
    catch_up_evidence_reason: str
    catch_up_schedule_name: str | None
    catch_up_runtime_minutes: int
    catch_up_summary: str
    catch_up_decision_at: str | None
    last_catch_up_decision: str
    active_flow_alert_count: int
    flow_alert_queue: str
    last_flow_alert_decision: str
    last_reconciliation: str | None
    last_moisture_write_status: str
    last_moisture_write_at: str | None
    last_moisture_write_schedule: str | None
    last_moisture_write_value: str | None
    last_refresh: str
    notes: tuple[str, ...]
    moisture_review_items: tuple[dict[str, object], ...]
    zone_overview_items: tuple[dict[str, object], ...]
    rain_source_candidates: tuple[dict[str, object], ...]
    rachio_weather_probe: dict[str, object] | None
    discovered_entities: dict[str, object]
    schedule_snapshots: tuple[ScheduleSnapshot, ...]


def event_dt(event: dict[str, object]) -> datetime:
    """Return the event timestamp in local time."""
    return dt_util.as_local(
        datetime.fromtimestamp(int(event["eventDate"]) / 1000, tz=timezone.utc)
    )


def summarize_event(event: dict[str, object] | None) -> str:
    """Summarize a Rachio event for display."""
    if not event:
        return "none"
    summary = str(event.get("summary", "")).strip()
    if summary:
        return summary
    subtype = str(event.get("subType", "")).strip()
    event_type = str(event.get("type", "")).strip()
    return f"{event_type} {subtype}".strip() or "event"


def latest_event_by_schedule(
    events: list[dict[str, object]],
    event_type: str,
    subtypes: tuple[str, ...],
) -> dict[str, dict[str, object]]:
    """Return the latest event for each schedule id."""
    result: dict[str, dict[str, object]] = {}
    for event in events:
        schedule_id = event.get("scheduleId")
        if not schedule_id:
            continue
        if event.get("type") != event_type:
            continue
        subtype = str(event.get("subType", ""))
        if subtypes and subtype not in subtypes:
            continue
        key = str(schedule_id)
        existing = result.get(key)
        if existing is None or int(event["eventDate"]) > int(existing["eventDate"]):
            result[key] = event
    return result


def parse_skip_summary(summary: str) -> tuple[float | None, float | None]:
    """Parse observed and threshold rain from a skip summary."""
    observed = threshold = None
    rain_match = RAIN_MM_RE.search(summary)
    if rain_match:
        observed = float(rain_match.group(1))
    threshold_match = THRESHOLD_MM_RE.search(summary)
    if threshold_match:
        threshold = float(threshold_match.group(1))
    return observed, threshold


def observed_rain_24h(
    events: list[dict[str, object]],
    current: datetime,
) -> tuple[str, str, dict[str, object] | None]:
    """Return the best observed rain from Rachio skip events in the last 24h."""
    window_start = current - timedelta(hours=24)
    best_event: dict[str, object] | None = None
    observed_event_count = 0
    latest_skip_event: dict[str, object] | None = None
    for event in events:
        if event.get("type") != "WEATHER_INTELLIGENCE":
            continue
        if "SKIP" not in str(event.get("subType", "")):
            continue
        happened_at = event_dt(event)
        if happened_at < window_start or happened_at > current:
            continue
        if latest_skip_event is None or int(event["eventDate"]) > int(
            latest_skip_event["eventDate"]
        ):
            latest_skip_event = event
        observed_mm, threshold_mm = parse_skip_summary(str(event.get("summary", "")))
        if observed_mm is None:
            continue
        observed_event_count += 1
        candidate = {
            "event_id": event.get("id"),
            "schedule_id": event.get("scheduleId"),
            "happened_at": happened_at.isoformat(),
            "observed_mm": observed_mm,
            "threshold_mm": threshold_mm,
            "summary": event.get("summary"),
            "window_start": window_start.isoformat(),
            "window_end": current.isoformat(),
            "observed_event_count": observed_event_count,
            "latest_skip_event_id": latest_skip_event.get("id")
            if latest_skip_event
            else None,
            "latest_skip_happened_at": event_dt(latest_skip_event).isoformat()
            if latest_skip_event
            else None,
            "latest_skip_summary": latest_skip_event.get("summary")
            if latest_skip_event
            else None,
        }
        if best_event is None or float(candidate["observed_mm"]) > float(
            best_event["observed_mm"]
        ):
            best_event = candidate
    if best_event is None:
        fallback = {
            "window_start": window_start.isoformat(),
            "window_end": current.isoformat(),
            "observed_event_count": observed_event_count,
            "latest_skip_event_id": latest_skip_event.get("id")
            if latest_skip_event
            else None,
            "latest_skip_happened_at": event_dt(latest_skip_event).isoformat()
            if latest_skip_event
            else None,
            "latest_skip_summary": latest_skip_event.get("summary")
            if latest_skip_event
            else None,
        }
        return "unknown", "not_reported", fallback
    return f"{float(best_event['observed_mm']):.2f}", "observed", best_event


def format_event_state(event: dict[str, object] | None) -> str:
    """Return a compact event state string for operator surfaces."""
    if not event:
        return "none"
    event_time = event_dt(event)
    return (
        f"{event_time:%Y-%m-%d %H:%M}|{event.get('type','')}|"
        f"{event.get('subType','')}|{event.get('summary','')}"
    )[:255]


def normalize_words(value: str) -> set[str]:
    """Normalize a string into lowercase word tokens."""
    return set(WORD_RE.findall(value.lower()))


def flow_alert_kind(summary: str) -> str | None:
    """Return low_flow/high_flow when an event summary describes a flow alert."""
    match = FLOW_ALERT_RE.search(summary)
    if not match:
        return None
    return f"{match.group('kind').lower()}_flow"


def flow_alert_zone_name(summary: str) -> str | None:
    """Parse a best-effort zone label from a flow-alert summary."""
    match = FLOW_ALERT_ZONE_RE.search(summary)
    if not match:
        return None
    zone_name = match.group("zone").strip(" .")
    return zone_name or None


def baseline_event(event: dict[str, object]) -> tuple[str, float] | None:
    """Parse a native Rachio flow-calibration baseline event."""
    match = FLOW_BASELINE_RE.search(str(event.get("summary", "")))
    if not match:
        return None
    return match.group("zone").strip(), float(match.group("flow"))


def event_matches_zone(event: dict[str, object], zone_name: str) -> bool:
    """Return whether event text appears to reference a zone by word overlap."""
    summary_words = normalize_words(str(event.get("summary", "")))
    zone_words = normalize_words(zone_name)
    if not summary_words or not zone_words:
        return False
    return len(summary_words & zone_words) >= min(2, len(zone_words))


def baseline_matches_zone(event: dict[str, object], zone_name: str) -> bool:
    """Return whether a parsed baseline event appears to belong to a zone."""
    parsed = baseline_event(event)
    if parsed is None:
        return False
    parsed_zone, _parsed_flow = parsed
    return event_matches_zone({"summary": parsed_zone}, zone_name)


def build_flow_alert_snapshots(
    events: list[dict[str, object]],
    controller: dict[str, object],
    acknowledged_flow_alert_ids: set[str],
) -> tuple[FlowAlertSnapshot, ...]:
    """Build review state for recent Rachio flow alerts."""
    zones = [
        zone
        for zone in controller.get("zones", [])
        if zone.get("enabled", True) and zone.get("id") and zone.get("name")
    ]
    flow_alerts: list[dict[str, object]] = []
    for event in events:
        summary = str(event.get("summary", ""))
        kind = flow_alert_kind(summary)
        if kind:
            candidate = dict(event)
            candidate["flow_alert_kind"] = kind
            flow_alerts.append(candidate)
    flow_alerts.sort(key=lambda event: int(event["eventDate"]), reverse=True)

    snapshots: list[FlowAlertSnapshot] = []
    seen: set[tuple[str, str]] = set()
    for event in flow_alerts:
        alert_summary = str(event.get("summary", ""))
        kind = str(event["flow_alert_kind"])
        matched_zone = next(
            (zone for zone in zones if event_matches_zone(event, str(zone.get("name", "")))),
            None,
        )
        zone_id = str(matched_zone.get("id")) if matched_zone else "unknown"
        zone_name = (
            str(matched_zone.get("name"))
            if matched_zone
            else flow_alert_zone_name(alert_summary) or "Unknown zone"
        )
        key = (zone_id, kind)
        if key in seen:
            continue
        seen.add(key)

        alert_time = event_dt(event)
        baseline_events = [
            baseline
            for baseline in events
            if baseline_event(baseline) is not None
            and event_dt(baseline) > alert_time
            and baseline_matches_zone(baseline, zone_name)
        ]
        baseline_events.sort(key=lambda baseline: int(baseline["eventDate"]))

        baseline_before = None
        previous_baselines = [
            baseline
            for baseline in events
            if baseline_event(baseline) is not None
            and event_dt(baseline) < alert_time
            and baseline_matches_zone(baseline, zone_name)
        ]
        previous_baselines.sort(key=lambda baseline: int(baseline["eventDate"]), reverse=True)
        if previous_baselines:
            parsed = baseline_event(previous_baselines[0])
            baseline_before = parsed[1] if parsed else None

        baseline_after = None
        calibration_at = None
        if baseline_events:
            parsed = baseline_event(baseline_events[-1])
            if parsed:
                baseline_after = parsed[1]
                calibration_at = event_dt(baseline_events[-1]).isoformat()

        delta_percent = None
        if baseline_before and baseline_after is not None:
            delta_percent = ((baseline_after - baseline_before) / baseline_before) * 100

        rule_id = f"flow|{zone_id}|{kind}|{int(event['eventDate'])}"
        if baseline_after is None:
            status = "calibration_required"
            reason = "A flow alert was seen and no later calibration baseline was found in the inspection window."
            recommended_action = "run_native_calibration"
        elif baseline_before is None:
            status = "calibrated_needs_review"
            reason = "A later calibration exists, but no earlier baseline was available for comparison."
            recommended_action = "review_baseline"
        elif abs((baseline_after - baseline_before) / baseline_before) <= FLOW_STABLE_TOLERANCE_RATIO:
            status = "normal_after_calibration"
            reason = "Post-alert calibration is within the stable-baseline tolerance."
            recommended_action = "clear_review"
        else:
            status = "problem_suspected"
            reason = "Post-alert calibration moved materially from the prior baseline."
            recommended_action = "inspect_zone"

        review_state = (
            "cleared" if rule_id in acknowledged_flow_alert_ids else "pending_review"
        )
        snapshots.append(
            FlowAlertSnapshot(
                rule_id=rule_id,
                zone_name=zone_name,
                alert_kind=kind,
                alert_at=alert_time.isoformat(),
                alert_summary=alert_summary,
                status=status,
                reason=reason,
                recommended_action=recommended_action,
                baseline_before_lpm=baseline_before,
                baseline_after_lpm=baseline_after,
                baseline_delta_percent=delta_percent,
                calibration_at=calibration_at,
                review_state=review_state,
                summary=(
                    f"{zone_name}: {kind.replace('_', ' ')} alert -> {status}"
                    if zone_name != "Unknown zone"
                    else f"{kind.replace('_', ' ')} alert -> {status}"
                ),
            )
        )
    return tuple(snapshots)


def webhook_matches(
    hook: dict[str, object],
    expected_webhook_id: str | None,
    expected_cloudhook_url: str | None,
) -> bool:
    """Return whether a Rachio webhook matches the linked HA webhook surface."""
    hook_id = str(hook.get("id", ""))
    hook_url = str(hook.get("url", ""))
    external_id = str(hook.get("externalId", ""))
    expected_host = ""
    if expected_cloudhook_url:
        expected_host = urllib.parse.urlparse(expected_cloudhook_url).netloc
    hook_host = urllib.parse.urlparse(hook_url).netloc

    if expected_webhook_id and hook_id == expected_webhook_id:
        return True
    if expected_cloudhook_url and hook_url == expected_cloudhook_url:
        return True
    if external_id.startswith(WEBHOOK_CONST_ID):
        if expected_host:
            return expected_host == hook_host
        return True
    return False


def match_schedule_entity(
    schedule_name: str,
    linked_entities: LinkedRachioEntities,
) -> ScheduleEntityRef | None:
    """Match a Rachio API schedule to a discovered HA schedule entity."""
    schedule_words = normalize_words(schedule_name)
    candidates: list[tuple[int, int, ScheduleEntityRef]] = []
    for entity in linked_entities.schedule_entities:
        entity_words = normalize_words(entity.label)
        overlap = len(schedule_words & entity_words)
        exactish = int(schedule_words == entity_words and bool(schedule_words))
        candidates.append((exactish, overlap, entity))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    if best[0] == 0 and best[1] == 0:
        return None
    return best[2]


def match_zone_entity(
    schedule_name: str,
    linked_entities: LinkedRachioEntities,
) -> ZoneEntityRef | None:
    """Match a Rachio API schedule to a discovered HA zone entity."""
    schedule_words = normalize_words(schedule_name)
    candidates: list[tuple[int, int, ZoneEntityRef]] = []
    for entity in linked_entities.zone_entities:
        entity_words = normalize_words(entity.label)
        overlap = len(schedule_words & entity_words)
        exactish = int(schedule_words == entity_words and bool(schedule_words))
        candidates.append((exactish, overlap, entity))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    if best[0] == 0 and best[1] == 0:
        return None
    return best[2]


def match_controller_zone(
    schedule_name: str,
    controller: dict[str, object],
) -> str | None:
    """Match a schedule name to a controller zone id by name overlap."""
    schedule_words = normalize_words(schedule_name)
    candidates: list[tuple[int, int, str]] = []
    for zone in controller.get("zones", []):
        if not zone.get("enabled", True):
            continue
        zone_name = str(zone.get("name", ""))
        zone_words = normalize_words(zone_name)
        overlap = len(schedule_words & zone_words)
        exactish = int(schedule_words == zone_words and bool(schedule_words))
        zone_id = str(zone.get("id", ""))
        if zone_id:
            candidates.append((exactish, overlap, zone_id))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    best = candidates[0]
    if best[0] == 0 and best[1] == 0:
        return None
    return best[2]


def resolve_moisture_entity(
    hass: HomeAssistant,
    mapped_entity_id: str | None,
) -> tuple[str | None, str | None, str, str | None]:
    """Resolve one explicit moisture entity mapping and derive a moisture band."""
    if not mapped_entity_id:
        return None, None, "unmapped", None

    state = hass.states.get(mapped_entity_id)
    if state is None:
        return mapped_entity_id, None, "missing", None
    state_last_updated = getattr(state, "last_updated", None)
    last_updated = state_last_updated.isoformat() if state_last_updated else None
    if state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
        return mapped_entity_id, str(state.state), "unavailable", last_updated
    try:
        numeric = float(state.state)
    except (TypeError, ValueError):
        return mapped_entity_id, str(state.state), "non_numeric", last_updated

    if numeric < DRY_THRESHOLD:
        band = "dry"
    elif numeric > WET_THRESHOLD:
        band = "wet"
    else:
        band = "target"
    return mapped_entity_id, f"{numeric:g}", band, last_updated


def _coerce_float(value: object) -> float | None:
    """Return a float for numeric-looking HA state/attribute values."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _normalise_key(value: str) -> str:
    """Normalise a Home Assistant attribute key for alias matching."""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _rain_unit(attributes: dict[str, object]) -> str | None:
    """Return the best available precipitation unit label."""
    return (
        attributes.get("precipitation_unit")
        or attributes.get("unit_of_measurement")
        or "mm"
    )


def _infer_sensor_window(entity_id: str, attributes: dict[str, object]) -> str:
    """Infer the reporting window for a numeric observed-rain sensor."""
    haystack = " ".join(
        [
            entity_id,
            str(attributes.get("friendly_name", "")),
            str(attributes.get("name", "")),
        ]
    ).lower()
    if "24" in haystack:
        return "24h"
    if "since 9" in haystack or "since_9" in haystack:
        return "since_9am"
    if "today" in haystack or "daily" in haystack:
        return "today"
    if "hour" in haystack:
        return "last_hour"
    return "configured_sensor"


def _resolve_rain_total_attribute(
    attributes: dict[str, object],
) -> tuple[str, float, str, str] | None:
    """Return the first numeric observed-rain total attribute."""
    normalised = {
        _normalise_key(str(key)): (str(key), value)
        for key, value in attributes.items()
    }
    for alias, (canonical_name, window, confidence) in RAIN_TOTAL_ATTRIBUTE_ALIASES.items():
        if alias not in normalised:
            continue
        source_name, attr_value = normalised[alias]
        numeric_attr = _coerce_float(attr_value)
        if numeric_attr is None:
            continue
        return source_name or canonical_name, numeric_attr, window, confidence
    return None


def _has_rain_rate_only(attributes: dict[str, object]) -> bool:
    """Return true when a source reports rate but not a usable total."""
    normalised = {_normalise_key(str(key)) for key in attributes}
    return bool(normalised & RAIN_RATE_ATTRIBUTE_ALIASES)


def resolve_rain_actuals_entity(
    hass: HomeAssistant,
    entity_id: str | None,
) -> RainActualsResolution:
    """Resolve a configured observed-rain source into value/unit/status/reason."""
    if not entity_id:
        return RainActualsResolution(
            value="unconfigured",
            unit=None,
            status="unconfigured",
            missing_input="rain_actuals_unconfigured",
            reason="No observed rainfall total entity is configured.",
            window="unconfigured",
            confidence="none",
        )
    state = hass.states.get(entity_id)
    if state is None:
        return RainActualsResolution(
            value="unavailable",
            unit=None,
            status="missing",
            missing_input="rain_actuals_missing",
            reason="Configured observed rainfall entity is missing.",
            window="unknown",
            confidence="none",
        )
    attributes = dict(getattr(state, "attributes", {}) or {})
    if state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
        return RainActualsResolution(
            value=str(state.state),
            unit=attributes.get("unit_of_measurement"),
            status="unavailable",
            missing_input="rain_actuals_unavailable",
            reason="Configured observed rainfall entity is not reporting a usable value.",
            window="unknown",
            confidence="none",
        )

    numeric_state = _coerce_float(state.state)

    if numeric_state is not None:
        window = _infer_sensor_window(str(entity_id), attributes)
        confidence = "high" if window == "24h" else "medium"
        return RainActualsResolution(
            value=f"{numeric_state:g}",
            unit=attributes.get("unit_of_measurement"),
            status="ok",
            missing_input=None,
            reason="Observed rainfall total resolved from a numeric Home Assistant entity.",
            window=window,
            confidence=confidence,
        )

    resolved_attribute = _resolve_rain_total_attribute(attributes)
    if resolved_attribute is not None:
        attr_name, numeric_attr, window, confidence = resolved_attribute
        return RainActualsResolution(
            value=f"{numeric_attr:g}",
            unit=_rain_unit(attributes),
            status="ok",
            missing_input=None,
            reason=f"Observed rainfall total resolved from the {attr_name} attribute.",
            window=window,
            confidence=confidence,
        )

    if _has_rain_rate_only(attributes):
        return RainActualsResolution(
            value="not_reported",
            unit=_rain_unit(attributes),
            status="rain_rate_only",
            missing_input="rain_actuals_rate_only",
            reason="Configured rain source exposes precipitation rate, but not an observed rainfall total.",
            window="instantaneous_rate",
            confidence="none",
        )

    if str(entity_id).startswith("weather."):
        return RainActualsResolution(
            value="not_reported",
            unit=attributes.get("precipitation_unit"),
            status="weather_no_observed_precipitation",
            missing_input="rain_actuals_weather_no_observed_precipitation",
            reason="Configured weather entity does not expose an observed rainfall total.",
            window="forecast_only",
            confidence="none",
        )

    return RainActualsResolution(
        value=str(state.state),
        unit=attributes.get("unit_of_measurement"),
        status="non_numeric",
        missing_input="rain_actuals_non_numeric",
        reason="Configured observed rainfall entity is not numeric.",
        window="unknown",
        confidence="none",
    )


def _iter_hass_states(hass: HomeAssistant) -> tuple[object, ...]:
    """Return all HA state objects when the state machine exposes them."""
    async_all = getattr(getattr(hass, "states", None), "async_all", None)
    if callable(async_all):
        return tuple(async_all())
    state_values = getattr(getattr(hass, "states", None), "_states", None)
    if isinstance(state_values, dict):
        return tuple(state_values.values())
    return ()


def discover_rain_source_candidates(
    hass: HomeAssistant,
    selected_entity_id: str | None = None,
) -> tuple[dict[str, object], ...]:
    """Discover plausible observed-rain sources already present in Home Assistant."""
    candidates: list[dict[str, object]] = []
    for state in _iter_hass_states(hass):
        entity_id = str(getattr(state, "entity_id", "") or "")
        if not entity_id:
            continue
        attributes = dict(getattr(state, "attributes", {}) or {})
        friendly_name = str(attributes.get("friendly_name", ""))
        haystack = f"{entity_id} {friendly_name}".lower()
        has_rain_name = any(word in haystack for word in RAIN_HINT_WORDS)
        has_precip_device_class = str(attributes.get("device_class", "")).lower() in {
            "precipitation",
            "precipitation_intensity",
        }
        has_rain_unit = str(attributes.get("unit_of_measurement", "")).lower() in {
            "mm",
            "in",
            "inch",
            "inches",
        }
        has_total_attr = _resolve_rain_total_attribute(attributes) is not None
        if not (has_rain_name or has_precip_device_class or has_rain_unit or has_total_attr):
            continue
        resolution = resolve_rain_actuals_entity(hass, entity_id)
        score = 0
        if entity_id == selected_entity_id:
            score += 100
        if resolution.status == "ok":
            score += 50
        if resolution.confidence == "high":
            score += 20
        elif resolution.confidence == "medium":
            score += 10
        if entity_id.startswith("sensor."):
            score += 8
        if has_precip_device_class:
            score += 6
        if has_rain_name:
            score += 4
        candidates.append(
            {
                "entity_id": entity_id,
                "name": friendly_name or entity_id,
                "state": str(getattr(state, "state", "")),
                "unit": resolution.unit,
                "status": resolution.status,
                "window": resolution.window,
                "confidence": resolution.confidence,
                "reason": resolution.reason,
                "selected": entity_id == selected_entity_id,
                "_score": score,
            }
        )
    candidates.sort(key=lambda item: (-int(item["_score"]), str(item["entity_id"])))
    for item in candidates:
        item.pop("_score", None)
    return tuple(candidates[:12])


def apply_moisture_mapping(
    hass: HomeAssistant,
    schedules: tuple[ScheduleSnapshot, ...],
    schedule_moisture_map: dict[str, str],
    acknowledged_recommendation_ids: set[str],
    auto_moisture_write_schedule_entities: set[str] | None = None,
    last_write_status_by_rule: dict[str, str] | None = None,
    write_back_mode_enabled: bool = True,
) -> tuple[ScheduleSnapshot, ...]:
    """Attach moisture mapping and banding to schedule snapshots."""
    auto_moisture_write_schedule_entities = auto_moisture_write_schedule_entities or set()
    last_write_status_by_rule = last_write_status_by_rule or {}
    hydrated: list[ScheduleSnapshot] = []
    for schedule in schedules:
        mapped_entity_id = (
            schedule_moisture_map.get(schedule.schedule_entity_id or "")
            if schedule.schedule_entity_id
            else None
        )
        (
            moisture_entity_id,
            moisture_value,
            moisture_band,
            moisture_last_updated,
        ) = resolve_moisture_entity(
            hass,
            mapped_entity_id,
        )
        if moisture_entity_id is None:
            moisture_status = "No explicit moisture sensor is mapped for this schedule."
        elif moisture_band in {"unavailable", "non_numeric", "missing"}:
            moisture_status = (
                "Mapped moisture sensor is not reporting a usable numeric value."
            )
        else:
            moisture_status = "Mapped moisture sensor resolved explicitly."
        if schedule.moisture_write_back_ready != "ready":
            recommended_action = "resolve_write_back"
        elif moisture_entity_id is None:
            recommended_action = "map_moisture_sensor"
        elif moisture_band in {"unavailable", "non_numeric", "missing"}:
            recommended_action = "repair_moisture_sensor"
        elif schedule.policy_mode == "auto_catch_up_enabled" and schedule.catch_up_candidate == "eligible_auto":
            recommended_action = "review_auto_catch_up"
        elif moisture_band == "dry":
            recommended_action = "write_moisture_now"
        else:
            recommended_action = "none"
        if recommended_action == "none":
            review_state = "clear"
        elif schedule.rule_id in acknowledged_recommendation_ids:
            review_state = "acknowledged"
        else:
            review_state = "pending_review"
        auto_write_enabled = bool(
            schedule.schedule_entity_id
            and schedule.schedule_entity_id in auto_moisture_write_schedule_entities
        )
        auto_write_status = "off"
        if auto_write_enabled:
            if not write_back_mode_enabled:
                auto_write_status = "blocked"
            elif (
                recommended_action == "write_moisture_now"
                and schedule.moisture_write_back_ready == "ready"
            ):
                auto_write_status = "eligible"
            elif recommended_action == "write_moisture_now":
                auto_write_status = "blocked"
            else:
                auto_write_status = "watching"
        write_value = (
            moisture_value if moisture_band in {"dry", "target", "wet"} else None
        )
        if write_value and schedule.moisture_write_back_ready == "ready":
            write_summary = f"Sensor {write_value}% -> Rachio zone moisture"
        elif write_value:
            write_summary = f"Sensor {write_value}% available; Rachio zone is not resolved"
        else:
            write_summary = "No usable moisture value to write"
        hydrated.append(
            ScheduleSnapshot(
                rule_id=schedule.rule_id,
                name=schedule.name,
                status=schedule.status,
                reason=schedule.reason,
                catch_up_candidate=schedule.catch_up_candidate,
                policy_mode=schedule.policy_mode,
                policy_basis=schedule.policy_basis,
                schedule_entity_id=schedule.schedule_entity_id,
                zone_entity_id=schedule.zone_entity_id,
                controller_zone_id=schedule.controller_zone_id,
                moisture_entity_id=moisture_entity_id,
                moisture_value=moisture_value,
                moisture_band=moisture_band,
                moisture_status=moisture_status,
                moisture_write_back_ready=schedule.moisture_write_back_ready,
                recommended_action=recommended_action,
                review_state=review_state,
                runtime_minutes=schedule.runtime_minutes,
                last_run_at=schedule.last_run_at,
                last_skip_at=schedule.last_skip_at,
                summary=schedule.summary,
                threshold_mm=schedule.threshold_mm,
                observed_mm=schedule.observed_mm,
                moisture_last_updated=moisture_last_updated,
                rachio_moisture_value=None,
                write_value=write_value,
                write_summary=write_summary,
                auto_moisture_write_enabled=auto_write_enabled,
                auto_moisture_write_status=auto_write_status,
                last_moisture_write_status=last_write_status_by_rule.get(schedule.rule_id),
            )
        )
    return tuple(hydrated)


def evaluate_cached_evidence_health(
    *,
    evidence: RachioEvidenceSnapshot | None,
    current: datetime,
) -> tuple[str, str, str]:
    """Return runtime health, reason, and webhook surface from cached evidence."""
    if evidence is None:
        return (
            "degraded",
            "Awaiting first reconcile.",
            "unknown",
        )
    if evidence.webhook_health != "registered":
        return (
            "degraded",
            "No valid Home Assistant-managed Rachio webhook is registered.",
            "registration_missing",
        )
    if evidence.last_event_at is None:
        return (
            "degraded",
            "No Rachio event history returned in the inspection window.",
            "stale",
        )
    latest_event_dt = datetime.fromisoformat(evidence.last_event_at)
    freshness = current - latest_event_dt
    if freshness > timedelta(hours=EXPECTED_EVENT_FRESHNESS_HOURS):
        return (
            "degraded",
            f"Latest Rachio event is older than {EXPECTED_EVENT_FRESHNESS_HOURS}h ({freshness}).",
            "stale",
        )
    return (
        "healthy",
        "Webhook registration present and event history is fresh.",
        "healthy",
    )


def moisture_action_label(action: str) -> str:
    """Return operator-facing copy for a moisture recommendation token."""
    return {
        "write_moisture_now": "Write ready",
        "resolve_write_back": "Resolve Rachio zone",
        "map_moisture_sensor": "Map sensor",
        "repair_moisture_sensor": "Repair sensor",
        "review_auto_catch_up": "Review catch-up",
        "none": "No write needed",
        "pending_moisture_eval": "Awaiting evaluation",
    }.get(action, action.replace("_", " ").title())


def moisture_data_quality(moisture_band: str) -> str:
    """Classify whether a mapped moisture reading is usable for decisions."""
    if moisture_band in {"dry", "target", "wet"}:
        return "ok"
    if moisture_band == "unmapped":
        return "unmapped"
    if moisture_band in {"missing", "unavailable", "non_numeric"}:
        return f"sensor_{moisture_band}"
    return "unknown"


def build_moisture_review_items(
    schedules: tuple[ScheduleSnapshot, ...],
) -> tuple[dict[str, object], ...]:
    """Build compact site-level moisture review items for dashboard use."""
    items: list[dict[str, object]] = []
    for schedule in schedules:
        if schedule.moisture_entity_id is None and schedule.moisture_band == "unmapped":
            continue
        if schedule.recommended_action == "write_moisture_now":
            posture_note = "Write-back recommended"
            rank = 0
        elif schedule.moisture_write_back_ready == "ready" and schedule.moisture_band == "dry":
            posture_note = "Write-back ready"
            rank = 1
        elif schedule.moisture_band in {"missing", "unavailable", "non_numeric"}:
            posture_note = "Sensor repair needed"
            rank = 3
        elif schedule.moisture_band == "wet":
            posture_note = "Wet / no write"
            rank = 2
        elif schedule.moisture_band == "target":
            posture_note = "Moisture watch"
            rank = 2
        elif schedule.moisture_band == "dry":
            posture_note = "Dry / review"
            rank = 1
        else:
            posture_note = "Unmapped"
            rank = 4
        write_value = schedule.write_value
        if write_value is None and schedule.moisture_band in {"dry", "target", "wet"}:
            write_value = schedule.moisture_value
        write_summary = schedule.write_summary
        if (
            write_summary == "No moisture write target."
            and write_value
            and schedule.moisture_write_back_ready == "ready"
        ):
            write_summary = f"Sensor {write_value}% -> Rachio zone moisture"
        items.append(
            {
                "schedule_name": schedule.name,
                "mapped_sensor": schedule.moisture_entity_id,
                "moisture_band": schedule.moisture_band,
                "posture_note": posture_note,
                "recommended_action": schedule.recommended_action,
                "recommended_action_label": moisture_action_label(
                    schedule.recommended_action
                ),
                "review_state": schedule.review_state,
                "moisture_write_back_ready": schedule.moisture_write_back_ready,
                "moisture_value": schedule.moisture_value,
                "sensor_value": schedule.moisture_value,
                "rachio_moisture_value": schedule.rachio_moisture_value or "not_reported",
                "write_value": write_value,
                "write_target_label": "Rachio zone moisture",
                "write_summary": write_summary,
                "can_write": bool(
                    schedule.moisture_write_back_ready == "ready"
                    and write_value is not None
                ),
                "auto_moisture_write_enabled": schedule.auto_moisture_write_enabled,
                "auto_moisture_write_status": schedule.auto_moisture_write_status,
                "last_moisture_write_status": schedule.last_moisture_write_status,
                "moisture_last_updated": schedule.moisture_last_updated,
                "data_quality": moisture_data_quality(schedule.moisture_band),
                "_rank": rank,
            }
        )
    items.sort(key=lambda item: (int(item["_rank"]), str(item["schedule_name"]).lower()))
    for item in items:
        item.pop("_rank", None)
    return tuple(items)


def _state_attr_value(hass: HomeAssistant, entity_id: str | None, keys: tuple[str, ...]) -> str | None:
    """Return the first non-empty attribute value from one HA entity."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    for key in keys:
        value = state.attributes.get(key)
        if value not in {None, ""}:
            return str(value)
    return None


def _state_attr_raw(hass: HomeAssistant, entity_id: str | None, keys: tuple[str, ...]) -> object | None:
    """Return the first non-empty raw attribute value from one HA entity."""
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return None
    for key in keys:
        value = state.attributes.get(key)
        if value is not None and value != "":
            return value
    return None


def _watering_days(value: object | None) -> list[str]:
    """Normalize schedule day metadata into compact day chips."""
    if value is None or value == "":
        return []
    day_map = {
        "monday": "M",
        "mon": "M",
        "m": "M",
        "tuesday": "T",
        "tue": "T",
        "tues": "T",
        "wednesday": "W",
        "wed": "W",
        "w": "W",
        "thursday": "Th",
        "thu": "Th",
        "thur": "Th",
        "thurs": "Th",
        "friday": "F",
        "fri": "F",
        "f": "F",
        "saturday": "Sa",
        "sat": "Sa",
        "sunday": "Su",
        "sun": "Su",
    }
    if isinstance(value, (list, tuple, set)):
        parts = [str(part).strip() for part in value]
    else:
        parts = re.split(r"[,/| ]+", str(value))
    chips: list[str] = []
    for part in parts:
        key = part.strip().lower()
        chip = day_map.get(key)
        if chip and chip not in chips:
            chips.append(chip)
    return chips


def _rain_skip_state(schedule: ScheduleSnapshot) -> str:
    """Return a compact rain-skip state for zone cards."""
    if not schedule.last_skip_at:
        return "none"
    if schedule.observed_mm is None:
        return "skipped_unknown_rain"
    if schedule.threshold_mm is not None and schedule.observed_mm >= schedule.threshold_mm:
        return "skipped_rain_satisfied"
    if schedule.threshold_mm is not None:
        return "skipped_rain_shortfall"
    return "skipped"


def _matching_flow_alert(
    schedule: ScheduleSnapshot,
    flow_alerts: tuple[FlowAlertSnapshot, ...],
) -> FlowAlertSnapshot | None:
    """Return the best pending flow alert for one schedule."""
    schedule_words = normalize_words(schedule.name)
    for alert in flow_alerts:
        if alert.review_state != "pending_review":
            continue
        alert_words = normalize_words(alert.zone_name)
        if not alert_words:
            continue
        if alert_words.issubset(schedule_words) or schedule_words.issubset(alert_words):
            return alert
    return None


def _existing_local_zone_image_path(hass: HomeAssistant, slug: str) -> str | None:
    """Return the local zone image URL only when the HA www file exists."""
    config = getattr(hass, "config", None)
    path_getter = getattr(config, "path", None)
    if not callable(path_getter):
        return None
    image_path = Path(path_getter("www", "rachio-supervisor", "zones", f"{slug}.jpg"))
    if image_path.exists():
        return f"/local/rachio-supervisor/zones/{slug}.jpg"
    return None


def _cached_imported_zone_image_path(hass: HomeAssistant, zone_id: str | None) -> str | None:
    """Return the imported Rachio image URL only when the cached file exists."""
    if not zone_id:
        return None
    config = getattr(hass, "config", None)
    path_getter = getattr(config, "path", None)
    if not callable(path_getter):
        return None
    image_path, image_url = imported_zone_photo_paths(path_getter, zone_id)
    if image_path.exists():
        return image_url
    return None


def build_zone_overview_items(
    hass: HomeAssistant,
    schedules: tuple[ScheduleSnapshot, ...],
    flow_alerts: tuple[FlowAlertSnapshot, ...] = (),
) -> tuple[dict[str, object], ...]:
    """Build compact, visual zone rows for dashboard use."""
    items: list[dict[str, object]] = []
    for index, schedule in enumerate(schedules, start=1):
        slug = "-".join(sorted(normalize_words(schedule.name))) or f"zone-{index}"
        local_image_path = _existing_local_zone_image_path(hass, slug)
        imported_image_path = schedule.imported_image_path or _cached_imported_zone_image_path(
            hass,
            schedule.controller_zone_id,
        )
        if local_image_path:
            image_path = local_image_path
            image_source = "local_override"
        elif imported_image_path:
            image_path = imported_image_path
            image_source = "rachio_import"
        else:
            image_path = ZONE_PLACEHOLDER_PATH
            image_source = "placeholder"
        next_run = _state_attr_value(
            hass,
            schedule.schedule_entity_id,
            (
                "next_run",
                "next_run_at",
                "next_scheduled_start",
                "next_start_time",
                "next_event",
            ),
        )
        watering_days = _watering_days(
            _state_attr_raw(
                hass,
                schedule.schedule_entity_id,
                (
                    "watering_days",
                    "days",
                    "schedule_days",
                    "weekdays",
                    "day_chips",
                ),
            )
        )
        plant_note = _state_attr_value(
            hass,
            schedule.schedule_entity_id,
            ("plant_note", "plants", "zone_note", "soil_note", "description"),
        )
        detail_note = _state_attr_value(
            hass,
            schedule.schedule_entity_id,
            ("detail_note", "watering_note", "emitters", "slope_note"),
        )
        schedule_state = "unknown"
        if schedule.schedule_entity_id:
            state = hass.states.get(schedule.schedule_entity_id)
            if state is not None:
                schedule_state = str(state.state)
        flow_alert = _matching_flow_alert(schedule, flow_alerts)
        flow_alert_state = flow_alert.status if flow_alert else "none"
        rain_skip_state = _rain_skip_state(schedule)
        if schedule.last_skip_at:
            water_badge = "skip"
            water_icon = "mdi:weather-rainy"
        elif schedule.status == "completed_recently":
            water_badge = "watered"
            water_icon = "mdi:water-check"
        else:
            water_badge = "watch"
            water_icon = "mdi:calendar-clock"
        if schedule.recommended_action == "write_moisture_now":
            supervisor_badge = "moisture"
            supervisor_icon = "mdi:water-percent-alert"
        elif flow_alert:
            supervisor_badge = "flow"
            supervisor_icon = "mdi:pipe-leak"
        elif schedule.catch_up_candidate in {
            "eligible_auto",
            "review_recommended",
            "missed_run_review",
        }:
            supervisor_badge = "catch-up"
            supervisor_icon = "mdi:sprinkler-variant"
        else:
            supervisor_badge = "ok"
            supervisor_icon = "mdi:check-circle-outline"
        items.append(
            {
                "zone_name": schedule.name,
                "schedule_name": schedule.name,
                "schedule_entity_id": schedule.schedule_entity_id,
                "zone_entity_id": schedule.zone_entity_id,
                "image_path": image_path,
                "image_source": image_source,
                "suggested_image_path": f"/local/rachio-supervisor/zones/{slug}.jpg",
                "fallback_image_path": ZONE_PLACEHOLDER_PATH,
                "rachio_image_available": schedule.rachio_image_available,
                "photo_import_status": schedule.photo_import_status,
                "photo_import_reason": schedule.photo_import_reason,
                "quick_run_minutes": schedule.runtime_minutes,
                "schedule_state": schedule_state,
                "next_run": next_run or "not_reported",
                "watering_days": watering_days,
                "last_run_at": schedule.last_run_at,
                "last_skip_at": schedule.last_skip_at,
                "rain_skip_state": rain_skip_state,
                "water_badge": water_badge,
                "water_icon": water_icon,
                "supervisor_badge": supervisor_badge,
                "supervisor_icon": supervisor_icon,
                "moisture_band": schedule.moisture_band,
                "moisture_value": schedule.moisture_value,
                "flow_alert_state": flow_alert_state,
                "flow_review_state": flow_alert_state,
                "policy_mode": schedule.policy_mode,
                "runtime_minutes": schedule.runtime_minutes,
                "plant_note": plant_note or "Add plants, soil, emitters, and frequency.",
                "detail_note": detail_note or schedule.summary,
            }
        )
    return tuple(items)


def choose_controller(
    devices: list[dict[str, object]],
    expected_zone_count: int,
    preferred_name: str,
) -> dict[str, object] | None:
    """Choose the best sprinkler controller for the linked site."""
    preferred_words = normalize_words(preferred_name)
    candidates: list[tuple[int, int, int, dict[str, object]]] = []
    for device in devices:
        zones = device.get("zones", [])
        if not isinstance(zones, list) or not zones:
            continue
        enabled_zones = [zone for zone in zones if zone.get("enabled", True)]
        enabled_count = len(enabled_zones)
        name_words = normalize_words(str(device.get("name", "")))
        overlap = len(preferred_words & name_words)
        score = -abs(enabled_count - expected_zone_count)
        candidates.append((overlap, score, enabled_count, device))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return candidates[0][3]


def _weather_probe_hints(
    payload: object,
    *,
    prefix: str,
    depth: int = 0,
    limit: int = 24,
) -> list[dict[str, str]]:
    """Return compact weather-related scalar hints from nested Rachio payloads."""
    if depth > 5 or limit <= 0:
        return []
    hints: list[dict[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            path_l = path.lower()
            if isinstance(value, (dict, list, tuple)):
                hints.extend(
                    _weather_probe_hints(
                        value,
                        prefix=path,
                        depth=depth + 1,
                        limit=limit - len(hints),
                    )
                )
            elif any(word in path_l for word in WEATHER_PROBE_HINT_WORDS):
                hints.append({"path": path, "value": str(value)[:160]})
            if len(hints) >= limit:
                return hints[:limit]
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload[:8]):
            path = f"{prefix}[{index}]"
            hints.extend(
                _weather_probe_hints(
                    value,
                    prefix=path,
                    depth=depth + 1,
                    limit=limit - len(hints),
                )
            )
            if len(hints) >= limit:
                return hints[:limit]
    return hints[:limit]


def build_rachio_weather_probe(
    controller: dict[str, object],
    forecast_payload: dict[str, object] | None,
) -> dict[str, object]:
    """Build diagnostics for Rachio weather-source hints without using forecasts as actuals."""
    hints = _weather_probe_hints(controller, prefix="controller")
    if forecast_payload:
        hints.extend(
            _weather_probe_hints(
                forecast_payload,
                prefix="forecast",
                limit=max(0, 24 - len(hints)),
            )
        )
    return {
        "status": "forecast_available" if forecast_payload else "forecast_unavailable",
        "source": "rachio_public_forecast",
        "used_for_actual_rain": False,
        "reason": (
            "Rachio forecast/source hints are diagnostic only; forecast precipitation is not treated as observed rainfall."
        ),
        "hints": hints[:24],
    }


def schedule_runtime_minutes(rule: dict[str, object]) -> int:
    """Return the total schedule runtime in whole minutes."""
    total_duration = rule.get("totalDuration")
    if isinstance(total_duration, int) and total_duration > 0:
        return max(1, round(total_duration / 60))
    return 1


def in_safe_window(current: datetime, safe_window_end_hour: int) -> bool:
    """Return whether the current local time is still inside the safe window."""
    return current.hour < safe_window_end_hour


def evaluate_catch_up_decision(
    *,
    current: datetime,
    schedules: tuple[ScheduleSnapshot, ...],
    controller_available: bool,
    rain_active: bool,
    rain_delay_active: bool,
    standby_active: bool,
    safe_window_end_hour: int,
    lockouts: dict[str, dict[str, object]],
) -> dict[str, object]:
    """Evaluate the current site-level catch-up decision."""
    latest_decision: dict[str, object] = {
        "status": "not_needed",
        "reason": "monitoring",
        "schedule_name": None,
        "zone_label": None,
        "zone_entity_id": None,
        "runtime_minutes": 0,
        "summary": "No active catch-up candidate.",
        "decision_key": f"monitoring|{current.date().isoformat()}",
        "event_id": None,
    }
    if not schedules:
        latest_decision["reason"] = "no_discovered_schedules"
        return latest_decision

    concrete_defers: list[dict[str, object]] = []
    confirmed: list[dict[str, object]] = []
    for schedule in schedules:
        decision_key = (
            f"{schedule.rule_id}|{schedule.last_skip_at or schedule.last_run_at or current.date().isoformat()}"
        )
        summary = schedule.summary or schedule.reason
        if schedule.policy_mode == "auto_catch_up_enabled":
            if schedule.catch_up_candidate == "eligible_auto":
                if not controller_available or standby_active:
                    concrete_defers.append(
                        {
                            "status": "deferred",
                            "reason": "controller_unavailable",
                            "schedule_name": schedule.name,
                            "zone_label": schedule.zone_entity_id or schedule.name,
                            "zone_entity_id": schedule.zone_entity_id,
                            "runtime_minutes": schedule.runtime_minutes,
                            "summary": summary,
                            "decision_key": decision_key,
                            "event_id": None,
                        }
                    )
                elif rain_active or rain_delay_active:
                    concrete_defers.append(
                        {
                            "status": "deferred",
                            "reason": "rain_satisfied",
                            "schedule_name": schedule.name,
                            "zone_label": schedule.zone_entity_id or schedule.name,
                            "zone_entity_id": schedule.zone_entity_id,
                            "runtime_minutes": schedule.runtime_minutes,
                            "summary": summary,
                            "decision_key": decision_key,
                            "event_id": None,
                        }
                    )
                elif decision_key in lockouts:
                    concrete_defers.append(
                        {
                            "status": "deferred",
                            "reason": "duplicate_event_lockout",
                            "schedule_name": schedule.name,
                            "zone_label": schedule.zone_entity_id or schedule.name,
                            "zone_entity_id": schedule.zone_entity_id,
                            "runtime_minutes": schedule.runtime_minutes,
                            "summary": summary,
                            "decision_key": decision_key,
                            "event_id": None,
                        }
                    )
                elif not in_safe_window(current, safe_window_end_hour):
                    concrete_defers.append(
                        {
                            "status": "deferred",
                            "reason": "outside_safe_window",
                            "schedule_name": schedule.name,
                            "zone_label": schedule.zone_entity_id or schedule.name,
                            "zone_entity_id": schedule.zone_entity_id,
                            "runtime_minutes": schedule.runtime_minutes,
                            "summary": summary,
                            "decision_key": decision_key,
                            "event_id": None,
                        }
                    )
                else:
                    confirmed.append(
                        {
                            "status": "confirmed",
                            "reason": "confirmed_skip",
                            "schedule_name": schedule.name,
                            "zone_label": schedule.zone_entity_id or schedule.name,
                            "zone_entity_id": schedule.zone_entity_id,
                            "runtime_minutes": schedule.runtime_minutes,
                            "summary": summary,
                            "decision_key": decision_key,
                            "event_id": None,
                        }
                    )
            elif schedule.catch_up_candidate == "not_needed":
                concrete_defers.append(
                    {
                        "status": "deferred",
                        "reason": "rain_satisfied",
                        "schedule_name": schedule.name,
                        "zone_label": schedule.zone_entity_id or schedule.name,
                        "zone_entity_id": schedule.zone_entity_id,
                        "runtime_minutes": schedule.runtime_minutes,
                        "summary": summary,
                        "decision_key": decision_key,
                        "event_id": None,
                    }
                )
        elif schedule.catch_up_candidate == "review_recommended":
            concrete_defers.append(
                {
                    "status": "deferred",
                    "reason": "review_recommended",
                    "schedule_name": schedule.name,
                    "zone_label": schedule.zone_entity_id or schedule.name,
                    "zone_entity_id": schedule.zone_entity_id,
                    "runtime_minutes": schedule.runtime_minutes,
                    "summary": summary,
                    "decision_key": decision_key,
                    "event_id": None,
                }
            )

    if confirmed:
        confirmed.sort(key=lambda item: (int(item["runtime_minutes"]), str(item["schedule_name"])))
        return confirmed[0]
    if concrete_defers:
        concrete_defers.sort(key=lambda item: str(item["schedule_name"]))
        return concrete_defers[0]
    return latest_decision


def build_rachio_evidence(
    client: RachioClient,
    linked_entities: LinkedRachioEntities,
    expected_zone_count: int,
    controller_available: bool,
    preferred_name: str,
    expected_webhook_id: str | None,
    expected_cloudhook_url: str | None,
    auto_catch_up_schedule_entities: set[str],
    auto_missed_run_schedule_entities: set[str],
    acknowledged_flow_alert_ids: set[str],
    import_zone_photos: bool = False,
    config_path=None,
) -> RachioEvidenceSnapshot:
    """Build a site-level evidence snapshot from the public Rachio API."""
    devices = client.list_person_devices()
    controller = choose_controller(devices, expected_zone_count, preferred_name)
    if controller is None:
        raise RachioClientError("No sprinkler controller with enabled zones was found.")

    controller_id = str(controller["id"])
    controller_name = str(controller.get("name", "Rachio Controller"))
    forecast_getter = getattr(client, "get_device_forecast", None)
    if callable(forecast_getter):
        try:
            forecast_payload = forecast_getter(controller_id, units="METRIC")
            weather_source_probe = build_rachio_weather_probe(controller, forecast_payload)
        except RachioClientError as err:
            weather_source_probe = build_rachio_weather_probe(controller, None)
            weather_source_probe["reason"] = (
                "Rachio forecast/source probe failed and remains diagnostic only: "
                f"{str(err)[:220]}"
            )
    else:
        weather_source_probe = build_rachio_weather_probe(controller, None)
        weather_source_probe["reason"] = (
            "Rachio forecast/source probe unavailable in the current API adapter."
        )
    now = dt_util.now()
    events = client.list_device_events(
        controller_id,
        start=now - timedelta(hours=EVENT_LOOKBACK_HOURS),
        end=now,
    )
    webhooks = client.list_device_webhooks(controller_id)
    matching_webhook = next(
        (
            hook
            for hook in webhooks
            if webhook_matches(hook, expected_webhook_id, expected_cloudhook_url)
        ),
        None,
    )
    if matching_webhook:
        webhook_health = "registered"
    elif webhooks:
        webhook_health = "mismatch"
    else:
        webhook_health = "missing"

    latest_event = max(events, key=lambda event: int(event["eventDate"]), default=None)
    latest_run = max(
        [
            event
            for event in events
            if event.get("type") in {"SCHEDULE_STATUS", "ZONE_STATUS"}
            and str(event.get("subType", "")).endswith(("STARTED", "COMPLETED", "STOPPED"))
        ],
        key=lambda event: int(event["eventDate"]),
        default=None,
    )
    latest_skip = max(
        [
            event
            for event in events
            if event.get("type") == "WEATHER_INTELLIGENCE"
            and "SKIP" in str(event.get("subType", ""))
        ],
        key=lambda event: int(event["eventDate"]),
        default=None,
    )
    observed_rain_state, observed_rain_status, observed_rain_best_event = observed_rain_24h(
        events,
        dt_util.now(),
    )

    completed_by_schedule = latest_event_by_schedule(
        events,
        "SCHEDULE_STATUS",
        ("SCHEDULE_COMPLETED",),
    )
    skipped_by_schedule = latest_event_by_schedule(
        events,
        "WEATHER_INTELLIGENCE",
        ("WEATHER_INTELLIGENCE_SKIP",),
    )

    schedule_snapshots: list[ScheduleSnapshot] = []
    for rule in controller.get("scheduleRules", []):
        if not rule.get("enabled"):
            continue
        rule_id = str(rule["id"])
        name = str(rule.get("name", rule_id))
        matched_schedule_entity = match_schedule_entity(name, linked_entities)
        matched_zone_entity = match_zone_entity(name, linked_entities)
        controller_zone_id = match_controller_zone(name, controller)
        imported_image_path = None
        photo_import_status = "disabled"
        photo_import_reason = None
        rachio_image_available = False
        if import_zone_photos and callable(config_path):
            slug = "-".join(sorted(normalize_words(name))) or f"zone-{len(schedule_snapshots) + 1}"
            local_override = Path(
                config_path("www", "rachio-supervisor", "zones", f"{slug}.jpg")
            )
            if local_override.exists():
                photo_import_status = "disabled"
            else:
                photo_result = import_rachio_zone_photo(
                    client=client,
                    zone_id=controller_zone_id,
                    config_path=config_path,
                    import_enabled=True,
                )
                photo_import_status = photo_result.status
                photo_import_reason = photo_result.reason
                rachio_image_available = photo_result.rachio_image_available
                imported_path, imported_url = imported_zone_photo_paths(
                    config_path,
                    controller_zone_id or "",
                )
                if imported_path.exists():
                    imported_image_path = imported_url
        schedule_entity_id = (
            matched_schedule_entity.entity_id if matched_schedule_entity else None
        )
        zone_entity_id = matched_zone_entity.entity_id if matched_zone_entity else None
        if schedule_entity_id and schedule_entity_id in auto_missed_run_schedule_entities:
            policy_mode = "auto_missed_run_enabled"
            policy_basis = "Configured missed-run recovery opt-in."
        elif schedule_entity_id and schedule_entity_id in auto_catch_up_schedule_entities:
            policy_mode = "auto_catch_up_enabled"
            policy_basis = "Configured automatic catch-up opt-in."
        else:
            policy_mode = "observe_only"
            policy_basis = "Default observe-first schedule posture."
        moisture_write_back_ready = (
            "ready" if controller_zone_id and zone_entity_id else "zone_unresolved"
        )
        run_event = completed_by_schedule.get(rule_id)
        skip_event = skipped_by_schedule.get(rule_id)
        observed_mm = threshold_mm = None
        if skip_event:
            observed_mm, threshold_mm = parse_skip_summary(str(skip_event.get("summary", "")))
        if run_event:
            status = "completed_recently"
            reason = summarize_event(run_event)
        elif skip_event:
            status = "skipped_recently"
            reason = summarize_event(skip_event)
        else:
            status = "monitoring"
            reason = "No recent completed or skipped schedule event in the inspection window."

        if skip_event and observed_mm is not None and threshold_mm is not None:
            if controller_available and observed_mm < threshold_mm:
                if policy_mode == "auto_catch_up_enabled":
                    candidate = "eligible_auto"
                else:
                    candidate = "review_recommended"
            else:
                candidate = "not_needed"
        elif (
            not skip_event
            and not run_event
            and policy_mode == "auto_missed_run_enabled"
        ):
            candidate = "missed_run_review"
        elif skip_event:
            candidate = "unknown"
        else:
            candidate = "not_applicable"

        schedule_snapshots.append(
            ScheduleSnapshot(
                rule_id=rule_id,
                name=name,
                status=status,
                reason=reason,
                catch_up_candidate=candidate,
                policy_mode=policy_mode,
                policy_basis=policy_basis,
                schedule_entity_id=schedule_entity_id,
                zone_entity_id=zone_entity_id,
                controller_zone_id=controller_zone_id,
                moisture_entity_id=None,
                moisture_value=None,
                moisture_band="unmapped",
                moisture_status="Moisture mapping not yet evaluated.",
                moisture_write_back_ready=moisture_write_back_ready,
                recommended_action="pending_moisture_eval",
                review_state="pending_moisture_eval",
                runtime_minutes=schedule_runtime_minutes(rule),
                last_run_at=event_dt(run_event).isoformat() if run_event else None,
                last_skip_at=event_dt(skip_event).isoformat() if skip_event else None,
                summary=reason,
                threshold_mm=threshold_mm,
                observed_mm=observed_mm,
                imported_image_path=imported_image_path,
                rachio_image_available=rachio_image_available,
                photo_import_status=photo_import_status,
                photo_import_reason=photo_import_reason,
            )
        )

    schedule_snapshots.sort(key=lambda snapshot: snapshot.name.lower())
    return RachioEvidenceSnapshot(
        controller_name=controller_name,
        controller_id=controller_id,
        last_event_summary=summarize_event(latest_event),
        last_event_at=event_dt(latest_event).isoformat() if latest_event else None,
        last_run_summary=summarize_event(latest_run),
        last_run_at=event_dt(latest_run).isoformat() if latest_run else None,
        last_skip_summary=summarize_event(latest_skip),
        last_skip_at=event_dt(latest_skip).isoformat() if latest_skip else None,
        observed_rain_24h=observed_rain_state,
        observed_rain_status=observed_rain_status,
        observed_rain_best_event=observed_rain_best_event,
        webhook_count=len(webhooks),
        webhook_health=webhook_health,
        webhook_url=str(matching_webhook.get("url", "")) if matching_webhook else None,
        webhook_external_id=str(matching_webhook.get("externalId", ""))
        if matching_webhook
        else None,
        flow_alert_snapshots=build_flow_alert_snapshots(
            events,
            controller,
            acknowledged_flow_alert_ids,
        ),
        schedule_snapshots=tuple(schedule_snapshots),
        weather_source_probe=weather_source_probe,
    )


class RachioSupervisorCoordinator(DataUpdateCoordinator[SupervisorSnapshot]):
    """Scaffold coordinator for the public seed."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.entry = entry
        self._cached_evidence: RachioEvidenceSnapshot | None = None
        self._last_moisture_write_status = "none"
        self._last_moisture_write_at: str | None = None
        self._last_moisture_write_schedule: str | None = None
        self._last_moisture_write_value: str | None = None
        self._acknowledged_recommendation_ids: set[str] = set()
        self._acknowledged_flow_alert_ids: set[str] = set()
        self._mode = "healthy"
        self._degraded_since: str | None = None
        self._healthy_reconciles = 0
        self._last_reconciliation: str | None = None
        self._last_success_at: str | None = None
        self._supervisor_reason = "Awaiting first reconcile."
        self._last_health_notification: str | None = None
        self._last_notified_decision_key: str | None = None
        self._lockouts: dict[str, dict[str, object]] = {}
        self._auto_moisture_write_lockouts: dict[str, dict[str, object]] = {}
        self._moisture_write_status_by_rule: dict[str, str] = {}
        self._latest_catch_up_decision: dict[str, object] = {
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

    def record_moisture_write(
        self,
        *,
        status: str,
        schedule_name: str | None,
        moisture_value: str | None,
        rule_id: str | None = None,
    ) -> None:
        """Record the most recent moisture write result."""
        self._last_moisture_write_status = status
        self._last_moisture_write_at = dt_util.now().isoformat()
        self._last_moisture_write_schedule = schedule_name
        self._last_moisture_write_value = moisture_value
        if rule_id:
            self._moisture_write_status_by_rule[rule_id] = status

    def set_recommendation_acknowledged(
        self,
        *,
        rule_id: str,
        acknowledged: bool,
    ) -> None:
        """Set or clear runtime acknowledgement for one schedule recommendation."""
        if acknowledged:
            self._acknowledged_recommendation_ids.add(rule_id)
        else:
            self._acknowledged_recommendation_ids.discard(rule_id)

    def clear_flow_alert_review(self, rule_id: str | None = None) -> None:
        """Clear one flow-alert review item, or all eligible current items.

        Only alerts that have a verified post-alert calibration within the
        stable-baseline tolerance may be cleared from the Supervisor review
        queue. Alerts that still require calibration, lack a comparable prior
        baseline, or show a material baseline change must remain active.
        """
        snapshots = (
            self._cached_evidence.flow_alert_snapshots if self._cached_evidence else ()
        )
        if rule_id:
            snapshot = next(
                (snapshot for snapshot in snapshots if snapshot.rule_id == rule_id),
                None,
            )
            if snapshot is None:
                raise ValueError("The requested flow alert review item was not found.")
            if snapshot.status != "normal_after_calibration":
                raise ValueError(
                    "Flow alert review can only be cleared after a normal post-alert calibration comparison."
                )
            self._acknowledged_flow_alert_ids.add(rule_id)
            return
        cleared_any = False
        for snapshot in snapshots:
            if snapshot.status == "normal_after_calibration":
                self._acknowledged_flow_alert_ids.add(snapshot.rule_id)
                cleared_any = True
        if not cleared_any and snapshots:
            raise ValueError(
                "No flow alert review items are currently eligible for clear. A normal post-alert calibration comparison is required first."
            )

    def _should_reconcile(self, current: datetime) -> bool:
        """Return whether a full Rachio reconcile should run right now."""
        if self._last_reconciliation is None:
            return True
        last_reconcile = datetime.fromisoformat(self._last_reconciliation)
        safe_window_end_hour = int(
            ({**self.entry.data, **self.entry.options}).get(
                CONF_SAFE_WINDOW_END_HOUR,
                DEFAULT_SAFE_WINDOW_END_HOUR,
            )
        )
        health_reconcile_hour = int(
            ({**self.entry.data, **self.entry.options}).get(
                CONF_HEALTH_RECONCILE_HOUR,
                DEFAULT_HEALTH_RECONCILE_HOUR,
            )
        )
        health_reconcile_minute = int(
            ({**self.entry.data, **self.entry.options}).get(
                CONF_HEALTH_RECONCILE_MINUTE,
                DEFAULT_HEALTH_RECONCILE_MINUTE,
            )
        )
        if self._mode == "degraded" and self._degraded_since:
            degraded_since = datetime.fromisoformat(self._degraded_since)
            if current - degraded_since < timedelta(hours=DEGRADED_FAST_WINDOW_HOURS):
                return current - last_reconcile >= timedelta(minutes=15)
            return current.minute == 0 and current - last_reconcile >= timedelta(
                minutes=55
            )
        if current.hour < safe_window_end_hour:
            return current - last_reconcile >= timedelta(minutes=10)
        if current.hour > health_reconcile_hour or (
            current.hour == health_reconcile_hour
            and current.minute >= health_reconcile_minute
        ):
            return last_reconcile.date() < current.date()
        return False

    def _apply_health_transition(self, health_state: str, current: datetime) -> str:
        """Update degraded/healthy mode bookkeeping and return effective mode."""
        mode = "degraded" if health_state != "healthy" else "healthy"
        if mode == "degraded":
            if self._mode != "degraded":
                self._degraded_since = current.isoformat()
            self._healthy_reconciles = 0
        else:
            if self._mode == "degraded":
                self._healthy_reconciles += 1
                if self._healthy_reconciles >= 2:
                    self._degraded_since = None
            else:
                self._healthy_reconciles = 0
        self._mode = "degraded" if self._degraded_since else mode
        return self._mode

    async def _async_update_notification(
        self,
        *,
        notification_id: str,
        title: str,
        message: str,
        dismiss_when: bool = False,
    ) -> None:
        """Create or dismiss a persistent notification."""
        if dismiss_when:
            await self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": notification_id},
                blocking=True,
            )
            return
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": title,
                "message": message,
                "notification_id": notification_id,
            },
            blocking=True,
        )

    async def _async_execute_auto_moisture_writes(
        self,
        *,
        linked_entry: ConfigEntry | None,
        api_key: object | None,
        schedules: tuple[ScheduleSnapshot, ...],
        current: datetime,
    ) -> None:
        """Execute explicitly enabled moisture write-back items conservatively."""
        if linked_entry is None or not api_key:
            return
        client = RachioClient(str(api_key))
        for schedule in schedules:
            if (
                not schedule.auto_moisture_write_enabled
                or schedule.auto_moisture_write_status != "eligible"
                or schedule.controller_zone_id is None
                or schedule.write_value is None
            ):
                continue
            try:
                moisture_percent = max(0.0, min(100.0, float(schedule.write_value)))
            except (TypeError, ValueError):
                self.record_moisture_write(
                    status="auto_rejected_non_numeric_moisture_value",
                    schedule_name=schedule.name,
                    moisture_value=schedule.write_value,
                    rule_id=schedule.rule_id,
                )
                continue

            lockout = self._auto_moisture_write_lockouts.get(schedule.rule_id)
            if lockout:
                last_at = datetime.fromisoformat(str(lockout["at"]))
                cooldown = timedelta(hours=AUTO_MOISTURE_WRITE_COOLDOWN_HOURS)
                if str(lockout.get("value")) == f"{moisture_percent:g}" and (
                    current - last_at < cooldown
                ):
                    self.record_moisture_write(
                        status="auto_skipped_cooldown",
                        schedule_name=schedule.name,
                        moisture_value=f"{moisture_percent:g}",
                        rule_id=schedule.rule_id,
                    )
                    continue

            try:
                await self.hass.async_add_executor_job(
                    client.set_zone_moisture_percent,
                    schedule.controller_zone_id,
                    moisture_percent,
                )
            except RachioClientError:
                self.record_moisture_write(
                    status="auto_rejected_api_error",
                    schedule_name=schedule.name,
                    moisture_value=f"{moisture_percent:g}",
                    rule_id=schedule.rule_id,
                )
                raise
            self._auto_moisture_write_lockouts[schedule.rule_id] = {
                "at": current.isoformat(),
                "value": f"{moisture_percent:g}",
            }
            self.record_moisture_write(
                status="auto_written",
                schedule_name=schedule.name,
                moisture_value=f"{moisture_percent:g}",
                rule_id=schedule.rule_id,
            )

    async def _async_execute_catch_up_decision(
        self,
        decision: dict[str, object],
        *,
        current: datetime,
        source: str,
    ) -> dict[str, object]:
        """Execute one confirmed catch-up decision through the HA Rachio service."""
        if decision.get("status") != "confirmed":
            raise ValueError("No confirmed catch-up decision is ready to run.")
        zone_entity_id = decision.get("zone_entity_id")
        if not zone_entity_id:
            raise ValueError("The current catch-up decision has no resolved zone entity.")
        decision_key = str(decision.get("decision_key") or "")
        if decision_key and decision_key in self._lockouts:
            raise ValueError("The current catch-up decision was already executed.")

        executed = dict(decision)
        executed["decision_at"] = executed.get("decision_at") or current.isoformat()
        await self.hass.services.async_call(
            "rachio",
            "start_watering",
            {
                "entity_id": str(zone_entity_id),
                "duration": int(executed.get("runtime_minutes", 0) or 0),
            },
            blocking=True,
        )
        executed["status"] = "executed"
        executed["execution_source"] = source
        self._lockouts[decision_key] = {
            "zone_label": executed.get("zone_label") or executed.get("schedule_name"),
            "decision_at": executed["decision_at"],
            "status": "executed",
            "source": source,
        }
        self._latest_catch_up_decision = executed
        return executed

    async def async_run_catch_up_now(self) -> None:
        """Run the current confirmed catch-up candidate as an explicit operator action."""
        await self.async_request_refresh()
        decision = self._latest_catch_up_decision
        executed = await self._async_execute_catch_up_decision(
            decision,
            current=dt_util.now(),
            source="manual_service",
        )
        self._latest_catch_up_decision = executed

    async def _async_update_data(self) -> SupervisorSnapshot:
        """Return the current site-level supervision snapshot."""
        current = dt_util.now()
        data = {**self.entry.data, **self.entry.options}
        observe_first = data.get(CONF_OBSERVE_FIRST, True)
        mode = "observe_only" if observe_first else "active_supervision"
        moisture_mode = data.get(CONF_ALLOW_MOISTURE_WRITE_BACK, False)
        notifications_enabled = data.get(
            CONF_ENABLE_PERSISTENT_NOTIFICATIONS,
            DEFAULT_ENABLE_PERSISTENT_NOTIFICATIONS,
        )
        safe_window_end_hour = int(
            data.get(CONF_SAFE_WINDOW_END_HOUR, DEFAULT_SAFE_WINDOW_END_HOUR)
        )
        action_posture = (
            "per_zone_opt_in_with_write_back_available"
            if moisture_mode
            else "per_zone_opt_in"
        )
        linked_entry = self.hass.config_entries.async_get_entry(
            data.get(CONF_RACHIO_CONFIG_ENTRY_ID, "")
        )
        linked_entry_title = linked_entry.title if linked_entry else "missing"
        linked_entry_state = linked_entry.state.value if linked_entry else "missing"
        linked_entities = discover_linked_entities(
            self.hass,
            data.get(CONF_RACHIO_CONFIG_ENTRY_ID, ""),
        )
        auto_catch_up_schedule_entities = {
            entity_id
            for entity_id in data.get(CONF_AUTO_CATCH_UP_SCHEDULES, [])
            if isinstance(entity_id, str)
        }
        auto_missed_run_schedule_entities = {
            entity_id
            for entity_id in data.get(CONF_AUTO_MISSED_RUN_SCHEDULES, [])
            if isinstance(entity_id, str)
        }
        auto_moisture_write_schedule_entities = {
            entity_id
            for entity_id in data.get(CONF_AUTO_MOISTURE_WRITE_SCHEDULES, [])
            if isinstance(entity_id, str)
        }
        schedule_moisture_map = {
            str(schedule_entity_id): str(moisture_entity_id)
            for schedule_entity_id, moisture_entity_id in data.get(
                CONF_SCHEDULE_MOISTURE_MAP, {}
            ).items()
            if schedule_entity_id and moisture_entity_id
        }
        notes: list[str] = []

        def state_value(entity_id: str | None) -> str:
            if not entity_id:
                return "missing"
            state = self.hass.states.get(entity_id)
            if state is None:
                return "missing"
            return str(state.state)

        def active_count(entity_ids: tuple[str, ...]) -> int:
            count = 0
            for entity_id in entity_ids:
                state = self.hass.states.get(entity_id)
                if state and state.state == "on":
                    count += 1
            return count

        missing_inputs: list[str] = []
        rain_actuals_entity = str(data.get(CONF_RAIN_ACTUALS_ENTITY, "") or "")
        rain_resolution = resolve_rain_actuals_entity(self.hass, rain_actuals_entity)
        rain_source_candidates = discover_rain_source_candidates(
            self.hass,
            rain_actuals_entity or None,
        )
        if rain_resolution.missing_input:
            missing_inputs.append(rain_resolution.missing_input)
        if rain_resolution.reason:
            notes.append(rain_resolution.reason)

        connectivity = state_value(linked_entities.connectivity_entity_id)
        rain_state = state_value(linked_entities.rain_entity_id)
        rain_delay_state = state_value(linked_entities.rain_delay_entity_id)
        standby_state = state_value(linked_entities.standby_entity_id)

        if linked_entry is None:
            notes.append("Linked Home Assistant Rachio config entry was not found.")
        elif linked_entry.state != ConfigEntryState.LOADED:
            notes.append(f"Linked Home Assistant Rachio entry is {linked_entry.state.value}.")
        if connectivity == "missing":
            notes.append("Connectivity entity could not be discovered from the linked Rachio entry.")
        if not linked_entities.zone_switches:
            notes.append("No zone switches were discovered from the linked Rachio entry.")

        if linked_entry and linked_entry.state == ConfigEntryState.LOADED:
            health = "degraded"
        elif linked_entry and linked_entry.state in {
            ConfigEntryState.SETUP_IN_PROGRESS,
            ConfigEntryState.NOT_LOADED,
        }:
            health = "degraded"
        else:
            health = "unavailable"

        controller_name = "unknown"
        controller_id = "unknown"
        last_event_summary = "unavailable"
        last_event_at = None
        last_run_summary = "unavailable"
        last_run_at = None
        last_skip_summary = "unavailable"
        last_skip_at = None
        observed_rain_24h = "unknown"
        observed_rain_status = "not_reported"
        observed_rain_best_event = None
        webhook_count = 0
        webhook_health = "unknown"
        webhook_url = None
        webhook_external_id = None
        flow_alert_snapshots: tuple[FlowAlertSnapshot, ...] = ()
        schedule_snapshots: tuple[ScheduleSnapshot, ...] = ()

        api_key = linked_entry.data.get(CONF_API_KEY) if linked_entry else None
        expected_webhook_id = linked_entry.data.get(CONF_WEBHOOK_ID) if linked_entry else None
        expected_cloudhook_url = (
            linked_entry.data.get(CONF_CLOUDHOOK_URL) if linked_entry else None
        )
        do_reconcile = self._should_reconcile(current)
        if not api_key:
            notes.append("Linked Rachio entry does not expose an API key to the supervisor.")
            self._supervisor_reason = "Linked Rachio entry does not expose an API key to the supervisor."
        elif linked_entry and linked_entry.state == ConfigEntryState.LOADED and (
            do_reconcile or self._cached_evidence is None
        ):
            try:
                evidence = await self.hass.async_add_executor_job(
                    build_rachio_evidence,
                    RachioClient(str(api_key)),
                    linked_entities,
                    len(linked_entities.zone_switches),
                    connectivity not in {"off", "missing", "unavailable"},
                    data.get(CONF_SITE_NAME, self.entry.title),
                    str(expected_webhook_id) if expected_webhook_id else None,
                    str(expected_cloudhook_url) if expected_cloudhook_url else None,
                    auto_catch_up_schedule_entities,
                    auto_missed_run_schedule_entities,
                    self._acknowledged_flow_alert_ids,
                    bool(
                        data.get(
                            CONF_IMPORT_RACHIO_ZONE_PHOTOS,
                            DEFAULT_IMPORT_RACHIO_ZONE_PHOTOS,
                        )
                    ),
                    self.hass.config.path,
                )
            except RachioClientError as err:
                notes.append(f"Rachio API evidence fetch failed: {err}")
                if health == "healthy":
                    health = "degraded"
                self._supervisor_reason = f"Rachio API evidence fetch failed: {err}"
            else:
                self._cached_evidence = evidence
                health, self._supervisor_reason, webhook_health = evaluate_cached_evidence_health(
                    evidence=evidence,
                    current=current,
                )
                effective_mode = self._apply_health_transition(health, current)
                self._last_reconciliation = current.isoformat()
                if health == "healthy":
                    self._last_success_at = self._last_reconciliation
                if notifications_enabled and self._last_health_notification != health:
                    await self._async_update_notification(
                        notification_id=f"{DOMAIN}_{self.entry.entry_id}_health",
                        title="Rachio Supervisor health",
                        message=self._supervisor_reason,
                        dismiss_when=health == "healthy",
                    )
                    self._last_health_notification = health
                notes.append(self._supervisor_reason)
        evidence = self._cached_evidence
        if evidence is not None:
            if linked_entry and linked_entry.state == ConfigEntryState.LOADED:
                health, self._supervisor_reason, cached_webhook_health = evaluate_cached_evidence_health(
                    evidence=evidence,
                    current=current,
                )
                if webhook_health == "unknown":
                    webhook_health = cached_webhook_health
                effective_mode = self._apply_health_transition(health, current)
            controller_name = evidence.controller_name
            controller_id = evidence.controller_id
            last_event_summary = evidence.last_event_summary
            last_event_at = evidence.last_event_at
            last_run_summary = evidence.last_run_summary
            last_run_at = evidence.last_run_at
            last_skip_summary = evidence.last_skip_summary
            last_skip_at = evidence.last_skip_at
            observed_rain_24h = evidence.observed_rain_24h
            observed_rain_status = evidence.observed_rain_status
            observed_rain_best_event = evidence.observed_rain_best_event
            webhook_count = evidence.webhook_count
            webhook_url = evidence.webhook_url
            webhook_external_id = evidence.webhook_external_id
            flow_alert_snapshots = evidence.flow_alert_snapshots
            if webhook_health == "unknown":
                webhook_health = (
                    "healthy"
                    if evidence.webhook_health == "registered"
                    else "registration_missing"
                )
            schedule_snapshots = apply_moisture_mapping(
                self.hass,
                evidence.schedule_snapshots,
                schedule_moisture_map,
                self._acknowledged_recommendation_ids,
                auto_moisture_write_schedule_entities,
                self._moisture_write_status_by_rule,
                bool(moisture_mode),
            )
            if moisture_mode and auto_moisture_write_schedule_entities:
                try:
                    await self._async_execute_auto_moisture_writes(
                        linked_entry=linked_entry,
                        api_key=api_key,
                        schedules=schedule_snapshots,
                        current=current,
                    )
                except RachioClientError as err:
                    notes.append(f"Automatic moisture write-back failed: {err}")
                    self._supervisor_reason = f"Automatic moisture write-back failed: {err}"
                schedule_snapshots = apply_moisture_mapping(
                    self.hass,
                    evidence.schedule_snapshots,
                    schedule_moisture_map,
                    self._acknowledged_recommendation_ids,
                    auto_moisture_write_schedule_entities,
                    self._moisture_write_status_by_rule,
                    bool(moisture_mode),
                )
            if not any(schedule.moisture_entity_id for schedule in schedule_snapshots):
                missing_inputs.append("no_active_schedule_moisture_mappings")
            if data.get(CONF_MOISTURE_SENSOR_ENTITIES, []) and not any(
                schedule.moisture_entity_id for schedule in schedule_snapshots
            ):
                notes.append(
                    "Candidate moisture sensors were configured, but no explicit schedule mapping is active."
                )
            for schedule in schedule_snapshots:
                if schedule.moisture_entity_id and schedule.moisture_band in {
                    "missing",
                    "unavailable",
                    "non_numeric",
                }:
                    missing_inputs.append(
                        f"moisture_sensor_problem:{schedule.name}:{schedule.moisture_band}"
                    )
            context_controller_available = connectivity not in {"off", "missing", "unavailable"}
            decision = evaluate_catch_up_decision(
                current=current,
                schedules=schedule_snapshots,
                controller_available=context_controller_available,
                rain_active=rain_state == "on",
                rain_delay_active=rain_delay_state == "on",
                standby_active=standby_state == "on",
                safe_window_end_hour=safe_window_end_hour,
                lockouts=self._lockouts,
            )
            decision["decision_at"] = current.isoformat()
            if (
                decision["status"] == "confirmed"
                and not observe_first
                and decision.get("zone_entity_id")
            ):
                decision = await self._async_execute_catch_up_decision(
                    decision,
                    current=current,
                    source="automatic_supervision",
                )
            self._latest_catch_up_decision = decision
            if notifications_enabled and decision["status"] in {"executed", "deferred"}:
                decision_key = str(decision["decision_key"])
                if self._last_notified_decision_key != decision_key:
                    schedule_name = decision.get("schedule_name") or "Irrigation zone"
                    if decision["status"] == "executed":
                        message = (
                            f"{schedule_name}: supervisor executed catch-up watering for "
                            f"{decision['runtime_minutes']} min.\n\n"
                            f"Reason: {decision['reason']}\n"
                            f"Evidence: {decision.get('summary','none')}"
                        )
                    else:
                        message = (
                            f"{schedule_name}: supervisor deferred catch-up.\n\n"
                            f"Reason: {decision['reason']}\n"
                            f"Evidence: {decision.get('summary','none')}"
                        )
                    await self._async_update_notification(
                        notification_id=f"{DOMAIN}_{self.entry.entry_id}_catchup",
                        title="Rachio Supervisor catch-up",
                        message=message,
                    )
                    self._last_notified_decision_key = decision_key

            active_flow_alerts = [
                alert
                for alert in flow_alert_snapshots
                if alert.review_state == "pending_review"
            ]
            if notifications_enabled and active_flow_alerts:
                alert = active_flow_alerts[0]
                await self._async_update_notification(
                    notification_id=f"{DOMAIN}_{self.entry.entry_id}_flow_alert",
                    title="Rachio Supervisor flow alert",
                    message=(
                        f"{alert.zone_name}: {alert.alert_kind.replace('_', ' ')}.\n\n"
                        f"Status: {alert.status}\n"
                        f"Action: {alert.recommended_action}\n"
                        f"Evidence: {alert.reason}"
                    ),
                )
            elif notifications_enabled:
                await self._async_update_notification(
                    notification_id=f"{DOMAIN}_{self.entry.entry_id}_flow_alert",
                    title="Rachio Supervisor flow alert",
                    message="Flow alert review cleared.",
                    dismiss_when=True,
                )

        ready_moisture_writes = [
            schedule
            for schedule in schedule_snapshots
            if schedule.moisture_write_back_ready == "ready"
            and schedule.moisture_band in {"dry", "target", "wet"}
            and schedule.moisture_value is not None
        ]
        ready_moisture_write_count = len(ready_moisture_writes)
        moisture_write_queue = (
            ", ".join(schedule.name for schedule in ready_moisture_writes[:5])
            if ready_moisture_writes
            else "none"
        )
        recommended_moisture_writes = [
            schedule
            for schedule in schedule_snapshots
            if schedule.recommended_action == "write_moisture_now"
        ]
        recommended_moisture_write_count = len(recommended_moisture_writes)
        recommended_moisture_write_queue = (
            ", ".join(schedule.name for schedule in recommended_moisture_writes[:5])
            if recommended_moisture_writes
            else "none"
        )
        active_recommendations = [
            schedule
            for schedule in schedule_snapshots
            if schedule.review_state == "pending_review"
        ]
        active_recommendation_count = len(active_recommendations)
        active_recommendation_queue = (
            ", ".join(schedule.name for schedule in active_recommendations[:5])
            if active_recommendations
            else "none"
        )
        acknowledged_recommendations = [
            schedule
            for schedule in schedule_snapshots
            if schedule.review_state == "acknowledged"
        ]
        acknowledged_recommendation_count = len(acknowledged_recommendations)
        acknowledged_recommendation_queue = (
            ", ".join(schedule.name for schedule in acknowledged_recommendations[:5])
            if acknowledged_recommendations
            else "none"
        )
        decision = self._latest_catch_up_decision
        catch_up_evidence_status = str(decision.get("status", "not_needed"))
        catch_up_evidence_reason = str(decision.get("reason", "monitoring"))
        catch_up_schedule_name = (
            str(decision.get("schedule_name"))
            if decision.get("schedule_name") is not None
            else None
        )
        catch_up_runtime_minutes = int(decision.get("runtime_minutes", 0) or 0)
        catch_up_summary = str(decision.get("summary", "No active catch-up candidate."))
        catch_up_decision_at = (
            str(decision.get("decision_at"))
            if decision.get("decision_at") is not None
            else None
        )
        last_catch_up_decision = (
            (
                f"{str(catch_up_decision_at)[:16].replace('T', ' ')}|"
                f"{catch_up_evidence_status}|"
                f"{catch_up_schedule_name or 'none'}|"
                f"{catch_up_evidence_reason}"
            )[:255]
            if catch_up_decision_at
            else "none"
        )
        active_flow_alerts = [
            alert
            for alert in flow_alert_snapshots
            if alert.review_state == "pending_review"
        ]
        active_flow_alert_count = len(active_flow_alerts)
        flow_alert_queue = (
            ", ".join(alert.zone_name for alert in active_flow_alerts[:5])
            if active_flow_alerts
            else "none"
        )
        latest_flow_alert = flow_alert_snapshots[0] if flow_alert_snapshots else None
        last_flow_alert_decision = (
            (
                f"{latest_flow_alert.alert_at[:16].replace('T', ' ')}|"
                f"{latest_flow_alert.alert_kind}|"
                f"{latest_flow_alert.zone_name}|"
                f"{latest_flow_alert.status}"
            )[:255]
            if latest_flow_alert
            else "none"
        )
        data_completeness = "complete" if not missing_inputs else "warnings"
        moisture_review_items = build_moisture_review_items(schedule_snapshots)
        zone_overview_items = build_zone_overview_items(
            self.hass, schedule_snapshots, flow_alert_snapshots
        )

        return SupervisorSnapshot(
            health=health,
            supervisor_mode=self._mode,
            supervisor_reason=self._supervisor_reason,
            data_completeness=data_completeness,
            missing_inputs=tuple(missing_inputs),
            runtime_integrity=health,
            mode=mode,
            action_posture=action_posture,
            site_name=data.get(CONF_SITE_NAME, self.entry.title),
            linked_entry_title=linked_entry_title,
            linked_entry_state=linked_entry_state,
            rachio_config_entry_id=data.get(CONF_RACHIO_CONFIG_ENTRY_ID, ""),
            rain_actuals_entity=data.get(CONF_RAIN_ACTUALS_ENTITY, ""),
            zone_count=int(data.get(CONF_ZONE_COUNT, 0)),
            configured_zone_count=len(linked_entities.zone_switches),
            active_zone_count=active_count(linked_entities.zone_switches),
            active_schedule_count=active_count(linked_entities.schedule_switches),
            connectivity=connectivity,
            rain_state=rain_state,
            rain_delay_state=rain_delay_state,
            standby_state=standby_state,
            actual_rain_value=rain_resolution.value,
            actual_rain_unit=rain_resolution.unit,
            rain_actuals_status=rain_resolution.status,
            rain_actuals_reason=rain_resolution.reason or "",
            rain_actuals_window=rain_resolution.window,
            rain_actuals_confidence=rain_resolution.confidence,
            controller_name=controller_name,
            controller_id=controller_id,
            last_event_summary=last_event_summary,
            last_event_at=last_event_at,
            last_run_summary=last_run_summary,
            last_run_at=last_run_at,
            last_skip_summary=last_skip_summary,
            last_skip_at=last_skip_at,
            observed_rain_24h=observed_rain_24h,
            observed_rain_status=observed_rain_status,
            observed_rain_best_event=observed_rain_best_event,
            webhook_count=webhook_count,
            webhook_health=webhook_health,
            webhook_url=webhook_url,
            webhook_external_id=webhook_external_id,
            ready_moisture_write_count=ready_moisture_write_count,
            moisture_write_queue=moisture_write_queue,
            recommended_moisture_write_count=recommended_moisture_write_count,
            recommended_moisture_write_queue=recommended_moisture_write_queue,
            active_recommendation_count=active_recommendation_count,
            active_recommendation_queue=active_recommendation_queue,
            acknowledged_recommendation_count=acknowledged_recommendation_count,
            acknowledged_recommendation_queue=acknowledged_recommendation_queue,
            catch_up_evidence_status=catch_up_evidence_status,
            catch_up_evidence_reason=catch_up_evidence_reason,
            catch_up_schedule_name=catch_up_schedule_name,
            catch_up_runtime_minutes=catch_up_runtime_minutes,
            catch_up_summary=catch_up_summary,
            catch_up_decision_at=catch_up_decision_at,
            last_catch_up_decision=last_catch_up_decision,
            active_flow_alert_count=active_flow_alert_count,
            flow_alert_queue=flow_alert_queue,
            last_flow_alert_decision=last_flow_alert_decision,
            last_reconciliation=self._last_reconciliation,
            last_moisture_write_status=self._last_moisture_write_status,
            last_moisture_write_at=self._last_moisture_write_at,
            last_moisture_write_schedule=self._last_moisture_write_schedule,
            last_moisture_write_value=self._last_moisture_write_value,
            last_refresh=current.isoformat(),
            notes=tuple(notes),
            moisture_review_items=moisture_review_items,
            zone_overview_items=zone_overview_items,
            rain_source_candidates=rain_source_candidates,
            rachio_weather_probe=evidence.weather_source_probe if evidence else None,
            discovered_entities={
                "connectivity": linked_entities.connectivity_entity_id,
                "rain": linked_entities.rain_entity_id,
                "rain_delay": linked_entities.rain_delay_entity_id,
                "standby": linked_entities.standby_entity_id,
                "zone_switches": list(linked_entities.zone_switches),
                "schedule_switches": list(linked_entities.schedule_switches),
                "entity_count": len(linked_entities.all_entities),
            },
            schedule_snapshots=schedule_snapshots,
        )
