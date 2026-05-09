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
    CONF_CLOUDHOOK_URL,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_SITE_NAME,
    CONF_WEBHOOK_ID,
    CONF_ZONE_COUNT,
    DOMAIN,
    WEBHOOK_CONST_ID,
)
from .discovery import discover_linked_entities
from .rachio_api import RachioClient, RachioClientError

TZ = ZoneInfo("UTC")
EVENT_LOOKBACK_HOURS = 96
WORD_RE = re.compile(r"[a-z0-9]+")

RAIN_MM_RE = re.compile(r"observed ([0-9.]+) mm(?: and predicted ([0-9.]+) mm)?")
THRESHOLD_MM_RE = re.compile(r"threshold of ([0-9.]+) mm")


@dataclass(slots=True)
class ScheduleSnapshot:
    """Schedule-level status snapshot."""

    rule_id: str
    name: str
    status: str
    reason: str
    catch_up_candidate: str
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
    expected_zone_count: int,
    actual_rain_value: str,
    controller_available: bool,
    preferred_name: str,
    expected_webhook_id: str | None,
    expected_cloudhook_url: str | None,
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
                candidate = "candidate"
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
                    len(linked_entities.zone_switches),
                    actual_rain_value,
                    connectivity not in {"off", "missing", "unavailable"},
                    data.get(CONF_SITE_NAME, self.entry.title),
                    str(expected_webhook_id) if expected_webhook_id else None,
                    str(expected_cloudhook_url) if expected_cloudhook_url else None,
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
                schedule_snapshots = evidence.schedule_snapshots
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
