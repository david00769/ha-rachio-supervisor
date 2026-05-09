"""Coordinator scaffold for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import urllib.parse
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    CONF_AUTO_CATCH_UP_SCHEDULES,
    CONF_CLOUDHOOK_URL,
    CONF_MOISTURE_SENSOR_ENTITIES,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_SCHEDULE_MOISTURE_MAP,
    CONF_SITE_NAME,
    CONF_WEBHOOK_ID,
    CONF_ZONE_COUNT,
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

TZ = ZoneInfo("UTC")
EVENT_LOOKBACK_HOURS = 96
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
    webhook_count: int
    webhook_health: str
    webhook_url: str | None
    webhook_external_id: str | None
    schedule_snapshots: tuple[ScheduleSnapshot, ...]


@dataclass(slots=True)
class SupervisorSnapshot:
    """Site-level public snapshot for the first runtime milestone."""

    health: str
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
    webhook_count: int
    webhook_health: str
    webhook_url: str | None
    webhook_external_id: str | None
    last_refresh: str
    notes: tuple[str, ...]
    discovered_entities: dict[str, object]
    schedule_snapshots: tuple[ScheduleSnapshot, ...]


def event_dt(event: dict[str, object]) -> datetime:
    """Return the event timestamp in UTC."""
    return datetime.fromtimestamp(int(event["eventDate"]) / 1000, tz=TZ)


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


def build_rachio_evidence(
    client: RachioClient,
    linked_entities: LinkedRachioEntities,
    expected_zone_count: int,
    actual_rain_value: str,
    controller_available: bool,
    preferred_name: str,
    expected_webhook_id: str | None,
    expected_cloudhook_url: str | None,
    auto_catch_up_schedule_entities: set[str],
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

    try:
        actual_rain_numeric = float(actual_rain_value)
    except (TypeError, ValueError):
        actual_rain_numeric = None

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
        if schedule_entity_id and schedule_entity_id in auto_catch_up_schedule_entities:
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

        if skip_event and actual_rain_numeric is not None and threshold_mm is not None:
            if controller_available and actual_rain_numeric < threshold_mm:
                if policy_mode == "auto_catch_up_enabled":
                    candidate = "eligible_auto"
                else:
                    candidate = "review_recommended"
            else:
                candidate = "not_needed"
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

    async def _async_update_data(self) -> SupervisorSnapshot:
        """Return the current site-level supervision snapshot."""
        data = {**self.entry.data, **self.entry.options}
        observe_first = data.get(CONF_OBSERVE_FIRST, True)
        mode = "observe_only" if observe_first else "manual_review"
        moisture_mode = data.get(CONF_ALLOW_MOISTURE_WRITE_BACK, False)
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
        if not api_key:
            notes.append("Linked Rachio entry does not expose an API key to the supervisor.")
        elif linked_entry and linked_entry.state == ConfigEntryState.LOADED:
            try:
                evidence = await self.hass.async_add_executor_job(
                    build_rachio_evidence,
                    RachioClient(str(api_key)),
                    linked_entities,
                    len(linked_entities.zone_switches),
                    actual_rain_value,
                    connectivity not in {"off", "missing", "unavailable"},
                    data.get(CONF_SITE_NAME, self.entry.title),
                    str(expected_webhook_id) if expected_webhook_id else None,
                    str(expected_cloudhook_url) if expected_cloudhook_url else None,
                    auto_catch_up_schedule_entities,
                )
            except RachioClientError as err:
                notes.append(f"Rachio API evidence fetch failed: {err}")
                if health == "healthy":
                    health = "degraded"
            else:
                controller_name = evidence.controller_name
                controller_id = evidence.controller_id
                last_event_summary = evidence.last_event_summary
                last_event_at = evidence.last_event_at
                last_run_summary = evidence.last_run_summary
                last_run_at = evidence.last_run_at
                last_skip_summary = evidence.last_skip_summary
                last_skip_at = evidence.last_skip_at
                webhook_count = evidence.webhook_count
                webhook_health = evidence.webhook_health
                webhook_url = evidence.webhook_url
                webhook_external_id = evidence.webhook_external_id
                schedule_snapshots = apply_moisture_mapping(
                    self.hass,
                    evidence.schedule_snapshots,
                    schedule_moisture_map,
                )
                if data.get(CONF_MOISTURE_SENSOR_ENTITIES, []) and not any(
                    schedule.moisture_entity_id for schedule in schedule_snapshots
                ):
                    notes.append(
                        "Candidate moisture sensors were configured, but no explicit schedule mapping is active."
                    )
                if webhook_health == "mismatch":
                    notes.append(
                        "Rachio controller has webhooks registered, but none matched the linked HA webhook id/url."
                    )
                elif webhook_health == "missing":
                    notes.append("No Rachio webhook registration was found for the linked controller.")
                if webhook_health != "registered" and health == "healthy":
                    health = "degraded"

        return SupervisorSnapshot(
            health=health,
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
            webhook_count=webhook_count,
            webhook_health=webhook_health,
            webhook_url=webhook_url,
            webhook_external_id=webhook_external_id,
            last_refresh=datetime.now(tz=TZ).isoformat(),
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
