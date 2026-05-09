"""Coordinator scaffold for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    CONF_AUTO_MISSED_RUN_SCHEDULES,
    CONF_CLOUDHOOK_URL,
    CONF_ENABLE_PERSISTENT_NOTIFICATIONS,
    CONF_HEALTH_RECONCILE_HOUR,
    CONF_HEALTH_RECONCILE_MINUTE,
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
from .rachio_api import RachioClient, RachioClientError

EVENT_LOOKBACK_HOURS = 96
EXPECTED_EVENT_FRESHNESS_HOURS = 36
DEGRADED_FAST_WINDOW_HOURS = 2
WORD_RE = re.compile(r"[a-z0-9]+")

RAIN_MM_RE = re.compile(r"observed ([0-9.]+) mm(?: and predicted ([0-9.]+) mm)?")
THRESHOLD_MM_RE = re.compile(r"threshold of ([0-9.]+) mm")
DRY_THRESHOLD = 25.0
WET_THRESHOLD = 60.0


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
    schedule_snapshots: tuple[ScheduleSnapshot, ...]


@dataclass(slots=True)
class SupervisorSnapshot:
    """Site-level public snapshot for the first runtime milestone."""

    health: str
    supervisor_mode: str
    supervisor_reason: str
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
    last_reconciliation: str | None
    last_moisture_write_status: str
    last_moisture_write_at: str | None
    last_moisture_write_schedule: str | None
    last_moisture_write_value: str | None
    last_refresh: str
    notes: tuple[str, ...]
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
) -> tuple[str | None, str | None, str]:
    """Resolve one explicit moisture entity mapping and derive a moisture band."""
    if not mapped_entity_id:
        return None, None, "unmapped"

    state = hass.states.get(mapped_entity_id)
    if state is None:
        return mapped_entity_id, None, "missing"
    if state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
        return mapped_entity_id, str(state.state), "unavailable"
    try:
        numeric = float(state.state)
    except (TypeError, ValueError):
        return mapped_entity_id, str(state.state), "non_numeric"

    if numeric < DRY_THRESHOLD:
        band = "dry"
    elif numeric > WET_THRESHOLD:
        band = "wet"
    else:
        band = "target"
    return mapped_entity_id, f"{numeric:g}", band


def apply_moisture_mapping(
    hass: HomeAssistant,
    schedules: tuple[ScheduleSnapshot, ...],
    schedule_moisture_map: dict[str, str],
    acknowledged_recommendation_ids: set[str],
) -> tuple[ScheduleSnapshot, ...]:
    """Attach moisture mapping and banding to schedule snapshots."""
    hydrated: list[ScheduleSnapshot] = []
    for schedule in schedules:
        mapped_entity_id = (
            schedule_moisture_map.get(schedule.schedule_entity_id or "")
            if schedule.schedule_entity_id
            else None
        )
        moisture_entity_id, moisture_value, moisture_band = resolve_moisture_entity(
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
            )
        )
    return tuple(hydrated)


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
) -> RachioEvidenceSnapshot:
    """Build a site-level evidence snapshot from the public Rachio API."""
    devices = client.list_person_devices()
    controller = choose_controller(devices, expected_zone_count, preferred_name)
    if controller is None:
        raise RachioClientError("No sprinkler controller with enabled zones was found.")

    controller_id = str(controller["id"])
    controller_name = str(controller.get("name", "Rachio Controller"))
    now = datetime.now(tz=TZ)
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
        schedule_snapshots=tuple(schedule_snapshots),
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
        self._mode = "healthy"
        self._degraded_since: str | None = None
        self._healthy_reconciles = 0
        self._last_reconciliation: str | None = None
        self._last_success_at: str | None = None
        self._supervisor_reason = "Awaiting first reconcile."
        self._last_health_notification: str | None = None
        self._last_notified_decision_key: str | None = None
        self._lockouts: dict[str, dict[str, object]] = {}
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
    ) -> None:
        """Record the most recent manual moisture write result."""
        self._last_moisture_write_status = status
        self._last_moisture_write_at = datetime.now(tz=TZ).isoformat()
        self._last_moisture_write_schedule = schedule_name
        self._last_moisture_write_value = moisture_value

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

        rain_state_obj = self.hass.states.get(data.get(CONF_RAIN_ACTUALS_ENTITY, ""))
        if rain_state_obj is None:
            actual_rain_value = "unavailable"
            actual_rain_unit = None
            rain_actuals_status = "missing"
            notes.append("Actual rain entity is missing or unavailable.")
        elif rain_state_obj.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            actual_rain_value = str(rain_state_obj.state)
            actual_rain_unit = rain_state_obj.attributes.get("unit_of_measurement")
            rain_actuals_status = "unavailable"
            notes.append("Actual rain entity is present but not reporting a usable value.")
        else:
            actual_rain_value = str(rain_state_obj.state)
            actual_rain_unit = rain_state_obj.attributes.get("unit_of_measurement")
            rain_actuals_status = "ok"

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

        if linked_entry and linked_entry.state == ConfigEntryState.LOADED and rain_actuals_status == "ok":
            health = "healthy"
        elif linked_entry and linked_entry.state in {
            ConfigEntryState.LOADED,
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
        schedule_snapshots: tuple[ScheduleSnapshot, ...] = ()

        api_key = linked_entry.data.get(CONF_API_KEY) if linked_entry else None
        expected_webhook_id = linked_entry.data.get(CONF_WEBHOOK_ID) if linked_entry else None
        expected_cloudhook_url = (
            linked_entry.data.get(CONF_CLOUDHOOK_URL) if linked_entry else None
        )
        do_reconcile = self._should_reconcile(current)
        if not api_key:
            notes.append("Linked Rachio entry does not expose an API key to the supervisor.")
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
                )
            except RachioClientError as err:
                notes.append(f"Rachio API evidence fetch failed: {err}")
                if health == "healthy":
                    health = "degraded"
                self._supervisor_reason = f"Rachio API evidence fetch failed: {err}"
            else:
                self._cached_evidence = evidence
                if evidence.webhook_health != "registered":
                    health = "degraded"
                    self._supervisor_reason = (
                        "No valid Home Assistant-managed Rachio webhook is registered."
                    )
                    webhook_health = "registration_missing"
                elif evidence.last_event_at is None:
                    health = "degraded"
                    self._supervisor_reason = (
                        "No Rachio event history returned in the inspection window."
                    )
                    webhook_health = "stale"
                else:
                    latest_event_dt = datetime.fromisoformat(evidence.last_event_at)
                    freshness = current - latest_event_dt
                    if freshness > timedelta(hours=EXPECTED_EVENT_FRESHNESS_HOURS):
                        health = "degraded"
                        self._supervisor_reason = (
                            f"Latest Rachio event is older than {EXPECTED_EVENT_FRESHNESS_HOURS}h ({freshness})."
                        )
                        webhook_health = "stale"
                    else:
                        health = "healthy"
                        self._supervisor_reason = (
                            "Webhook registration present and event history is fresh."
                        )
                        webhook_health = "healthy"
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
            )
            if data.get(CONF_MOISTURE_SENSOR_ENTITIES, []) and not any(
                schedule.moisture_entity_id for schedule in schedule_snapshots
            ):
                notes.append(
                    "Candidate moisture sensors were configured, but no explicit schedule mapping is active."
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
                await self.hass.services.async_call(
                    "rachio",
                    "start_watering",
                    {
                        "entity_id": decision["zone_entity_id"],
                        "duration": {"minutes": int(decision["runtime_minutes"])},
                    },
                    blocking=True,
                )
                decision["status"] = "executed"
                self._lockouts[str(decision["decision_key"])] = {
                    "zone_label": decision.get("zone_label") or decision.get("schedule_name"),
                    "decision_at": decision["decision_at"],
                    "status": "executed",
                }
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

        return SupervisorSnapshot(
            health=health,
            supervisor_mode=self._mode,
            supervisor_reason=self._supervisor_reason,
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
            actual_rain_value=actual_rain_value,
            actual_rain_unit=actual_rain_unit,
            rain_actuals_status=rain_actuals_status,
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
            last_reconciliation=self._last_reconciliation,
            last_moisture_write_status=self._last_moisture_write_status,
            last_moisture_write_at=self._last_moisture_write_at,
            last_moisture_write_schedule=self._last_moisture_write_schedule,
            last_moisture_write_value=self._last_moisture_write_value,
            last_refresh=current.isoformat(),
            notes=tuple(notes),
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
