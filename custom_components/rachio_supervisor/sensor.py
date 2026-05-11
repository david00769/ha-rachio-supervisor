"""Sensor platform for Rachio Supervisor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RachioSupervisorCoordinator, SupervisorSnapshot
from .entity import RachioSupervisorEntity

SITE_SENSOR_NAMES = {
    "health": "Health",
    "webhook_health": "Webhook health",
    "supervisor_mode": "Supervisor mode",
    "mode": "Operating mode",
    "linked_rachio_entry": "Linked Rachio entry",
    "action_posture": "Action posture",
    "rain_actuals_source": "Rain actuals source",
    "actual_rain_24h": "Actual rain, 24h",
    "observed_rain_24h": "Observed rain, 24h",
    "last_event": "Last event",
    "last_run": "Last run",
    "last_run_event": "Last run event",
    "last_skip": "Last skip",
    "last_skip_decision": "Last skip decision",
    "active_zone_count": "Active zones",
    "configured_zone_count": "Configured zones",
    "zone_overview": "Zone overview",
    "last_reconciliation": "Last reconciliation",
    "last_refresh": "Last refresh",
    "last_moisture_write": "Last moisture write",
    "ready_moisture_write_count": "Ready moisture writes",
    "moisture_write_queue": "Moisture write queue",
    "recommended_moisture_write_count": "Recommended moisture writes",
    "recommended_moisture_write_queue": "Recommended moisture queue",
    "active_recommendation_count": "Active recommendations",
    "active_recommendation_queue": "Active recommendation queue",
    "acknowledged_recommendation_count": "Acknowledged recommendations",
    "acknowledged_recommendation_queue": "Acknowledged recommendation queue",
    "catch_up_evidence": "Catch-up evidence",
    "last_catch_up_decision": "Last catch-up decision",
    "active_flow_alert_count": "Active flow alerts",
    "flow_alert_queue": "Flow alert queue",
    "last_flow_alert_decision": "Last flow alert decision",
}

PHOTO_IMPORT_STATUSES = (
    "disabled",
    "cached",
    "imported",
    "missing",
    "rejected",
    "failed",
)


def _format_at_local(value: str | None) -> str:
    """Format one ISO timestamp for compact local display."""
    if not value or value == "never":
        return "none"
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return str(value)[:16]


def _compact_run_summary(summary: str) -> tuple[str | None, str]:
    """Compact a run-style summary into subject and brief text."""
    if " ran for " in summary:
        subject, remainder = summary.split(" ran for ", 1)
        minutes = remainder.replace(" minutes.", " min").replace(" minute.", " min")
        return subject.strip(), f"ran {minutes}".strip()
    return None, summary


def _compact_skip_summary(summary: str) -> tuple[str | None, str]:
    """Compact a skip-style summary into subject and brief text."""
    if " was scheduled" in summary:
        subject = summary.split(" was scheduled", 1)[0].strip()
        brief = "skip: weather/soil"
        if "rain" in summary.lower():
            brief = "skip: rain"
        return subject, brief
    return None, summary


def _decision_compact_attrs(
    *,
    label: str,
    summary: str,
    at_local: str | None,
) -> dict[str, object]:
    """Build compact dashboard-facing fields for one decision sensor."""
    subject = label
    brief = summary
    if label in {"Last event", "Last run event", "Last run"}:
        compact_subject, brief = _compact_run_summary(summary)
        if compact_subject:
            subject = compact_subject
    elif label in {"Last skip decision", "Last skip"}:
        compact_subject, brief = _compact_skip_summary(summary)
        if compact_subject:
            subject = compact_subject
    elif label == "Last reconciliation":
        subject = "Supervisor"
        brief = at_local or "none"
    return {
        "subject": subject,
        "brief": brief,
        "at_local": at_local or "none",
    }


def _photo_import_counts(items: list[dict[str, object]]) -> dict[str, int]:
    """Return dashboard-facing counts for zone photo import outcomes."""
    counts = {status: 0 for status in PHOTO_IMPORT_STATUSES}
    for item in items:
        status = str(item.get("photo_import_status") or "disabled")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _photo_import_summary(counts: dict[str, int]) -> str:
    """Return a compact operator summary for photo import state."""
    parts = [
        f"{counts[status]} {status}"
        for status in PHOTO_IMPORT_STATUSES
        if counts.get(status)
    ]
    return ", ".join(parts) if parts else "no zone photo metadata"


@dataclass(frozen=True, kw_only=True)
class RachioSupervisorSensorDescription(SensorEntityDescription):
    """Description for scaffold sensors."""

    value_fn: Callable[[SupervisorSnapshot], str]


DESCRIPTIONS = (
    RachioSupervisorSensorDescription(
        key="health",
        translation_key="health",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.health,
    ),
    RachioSupervisorSensorDescription(
        key="webhook_health",
        translation_key="webhook_health",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.webhook_health,
    ),
    RachioSupervisorSensorDescription(
        key="supervisor_mode",
        translation_key="supervisor_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.supervisor_mode,
    ),
    RachioSupervisorSensorDescription(
        key="mode",
        translation_key="mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.mode,
    ),
    RachioSupervisorSensorDescription(
        key="linked_rachio_entry",
        translation_key="linked_rachio_entry",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.linked_entry_title,
    ),
    RachioSupervisorSensorDescription(
        key="action_posture",
        translation_key="action_posture",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.action_posture,
    ),
    RachioSupervisorSensorDescription(
        key="rain_actuals_source",
        translation_key="rain_actuals_source",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.rain_actuals_entity or "unconfigured",
    ),
    RachioSupervisorSensorDescription(
        key="actual_rain_24h",
        translation_key="actual_rain_24h",
        value_fn=lambda data: data.actual_rain_value,
    ),
    RachioSupervisorSensorDescription(
        key="observed_rain_24h",
        translation_key="observed_rain_24h",
        value_fn=lambda data: data.observed_rain_24h,
    ),
    RachioSupervisorSensorDescription(
        key="last_event",
        translation_key="last_event",
        value_fn=lambda data: data.last_event_summary,
    ),
    RachioSupervisorSensorDescription(
        key="last_run",
        translation_key="last_run",
        value_fn=lambda data: data.last_run_summary,
    ),
    RachioSupervisorSensorDescription(
        key="last_run_event",
        translation_key="last_run_event",
        value_fn=lambda data: data.last_run_summary,
    ),
    RachioSupervisorSensorDescription(
        key="last_skip",
        translation_key="last_skip",
        value_fn=lambda data: data.last_skip_summary,
    ),
    RachioSupervisorSensorDescription(
        key="last_skip_decision",
        translation_key="last_skip_decision",
        value_fn=lambda data: data.last_skip_summary,
    ),
    RachioSupervisorSensorDescription(
        key="active_zone_count",
        translation_key="active_zone_count",
        value_fn=lambda data: str(data.active_zone_count),
    ),
    RachioSupervisorSensorDescription(
        key="configured_zone_count",
        translation_key="configured_zone_count",
        value_fn=lambda data: str(data.configured_zone_count),
    ),
    RachioSupervisorSensorDescription(
        key="zone_overview",
        translation_key="zone_overview",
        value_fn=lambda data: str(len(data.zone_overview_items)),
    ),
    RachioSupervisorSensorDescription(
        key="last_reconciliation",
        translation_key="last_reconciliation",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_reconciliation or "never",
    ),
    RachioSupervisorSensorDescription(
        key="last_refresh",
        translation_key="last_refresh",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_refresh,
    ),
    RachioSupervisorSensorDescription(
        key="last_moisture_write",
        translation_key="last_moisture_write",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_moisture_write_status,
    ),
    RachioSupervisorSensorDescription(
        key="ready_moisture_write_count",
        translation_key="ready_moisture_write_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: str(data.ready_moisture_write_count),
    ),
    RachioSupervisorSensorDescription(
        key="moisture_write_queue",
        translation_key="moisture_write_queue",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.moisture_write_queue,
    ),
    RachioSupervisorSensorDescription(
        key="recommended_moisture_write_count",
        translation_key="recommended_moisture_write_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: str(data.recommended_moisture_write_count),
    ),
    RachioSupervisorSensorDescription(
        key="recommended_moisture_write_queue",
        translation_key="recommended_moisture_write_queue",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.recommended_moisture_write_queue,
    ),
    RachioSupervisorSensorDescription(
        key="active_recommendation_count",
        translation_key="active_recommendation_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: str(data.active_recommendation_count),
    ),
    RachioSupervisorSensorDescription(
        key="active_recommendation_queue",
        translation_key="active_recommendation_queue",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.active_recommendation_queue,
    ),
    RachioSupervisorSensorDescription(
        key="acknowledged_recommendation_count",
        translation_key="acknowledged_recommendation_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: str(data.acknowledged_recommendation_count),
    ),
    RachioSupervisorSensorDescription(
        key="acknowledged_recommendation_queue",
        translation_key="acknowledged_recommendation_queue",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.acknowledged_recommendation_queue,
    ),
    RachioSupervisorSensorDescription(
        key="catch_up_evidence",
        translation_key="catch_up_evidence",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.catch_up_evidence_status,
    ),
    RachioSupervisorSensorDescription(
        key="last_catch_up_decision",
        translation_key="last_catch_up_decision",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_catch_up_decision,
    ),
    RachioSupervisorSensorDescription(
        key="active_flow_alert_count",
        translation_key="active_flow_alert_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: str(data.active_flow_alert_count),
    ),
    RachioSupervisorSensorDescription(
        key="flow_alert_queue",
        translation_key="flow_alert_queue",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.flow_alert_queue,
    ),
    RachioSupervisorSensorDescription(
        key="last_flow_alert_decision",
        translation_key="last_flow_alert_decision",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.last_flow_alert_decision,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scaffold sensors."""
    coordinator: RachioSupervisorCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [RachioSupervisorSensor(coordinator, description) for description in DESCRIPTIONS]
    entities.extend(
        RachioSupervisorScheduleSensor(coordinator, schedule, suffix, label)
        for schedule in coordinator.data.schedule_snapshots
        for suffix, label in (
            ("status", "Status"),
            ("reason", "Reason"),
            ("policy_mode", "Policy"),
            ("moisture_band", "Moisture"),
            ("moisture_write_back_ready", "Write-back"),
            ("recommended_action", "Recommendation"),
            ("review_state", "Review"),
            ("catch_up_candidate", "Catch-up candidate"),
        )
    )
    async_add_entities(entities)


class RachioSupervisorSensor(RachioSupervisorEntity, SensorEntity):
    """Scaffold sensor entity."""

    entity_description: RachioSupervisorSensorDescription

    def __init__(
        self,
        coordinator: RachioSupervisorCoordinator,
        description: RachioSupervisorSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        # Custom integrations can lose translation-derived names during early
        # shadow installs and then register generic entity IDs like
        # `sensor.sugarloaf_8`. Set the public name explicitly so a fresh entry
        # gets stable, parity-friendly entity IDs.
        self._attr_name = SITE_SENSOR_NAMES[description.key]
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> str:
        """Return the current sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return contextual attributes for the current sensor."""
        data = self.coordinator.data
        if self.entity_description.key == "health":
            return {
                "plain_english": "Overall supervisor runtime integrity: linked entry, webhook registration, event freshness, and reconcile/API health.",
                "supervisor_mode": data.supervisor_mode,
                "supervisor_reason": data.supervisor_reason,
                "data_completeness": data.data_completeness,
                "missing_inputs": list(data.missing_inputs),
                "runtime_integrity": data.runtime_integrity,
                "linked_entry_title": data.linked_entry_title,
                "linked_entry_state": data.linked_entry_state,
                "connectivity": data.connectivity,
                "rain_state": data.rain_state,
                "rain_delay_state": data.rain_delay_state,
                "standby_state": data.standby_state,
                "controller_name": data.controller_name,
                "controller_id": data.controller_id,
                "webhook_count": data.webhook_count,
                "notes": list(data.notes),
            }
        if self.entity_description.key == "webhook_health":
            return {
                "plain_english": "Whether the Home Assistant-managed Rachio webhook registration still looks valid and current.",
                "webhook_count": data.webhook_count,
                "webhook_url": data.webhook_url,
                "webhook_external_id": data.webhook_external_id,
                "linked_entry_state": data.linked_entry_state,
                "supervisor_reason": data.supervisor_reason,
                "runtime_integrity": data.runtime_integrity,
            }
        if self.entity_description.key == "supervisor_mode":
            return {
                "supervisor_reason": data.supervisor_reason,
                "last_reconciliation": data.last_reconciliation,
            }
        if self.entity_description.key == "actual_rain_24h":
            return {
                "unit_of_measurement": data.actual_rain_unit,
                "status": data.rain_actuals_status,
                "reason": data.rain_actuals_reason,
                "window": data.rain_actuals_window,
                "confidence": data.rain_actuals_confidence,
                "source_entity": data.rain_actuals_entity,
                "candidate_sources": list(data.rain_source_candidates),
                "rachio_weather_probe": data.rachio_weather_probe,
            }
        if self.entity_description.key == "zone_overview":
            zones = list(data.zone_overview_items)
            photo_counts = _photo_import_counts(zones)
            return {
                "zones": zones,
                "image_path_convention": "/local/rachio-supervisor/zones/<zone-slug>.jpg",
                "fallback_image_path": "/rachio_supervisor/zone-placeholder.svg",
                "quick_run_service": "rachio_supervisor.quick_run_zone",
                "photo_import_counts": photo_counts,
                "photo_import_summary": _photo_import_summary(photo_counts),
            }
        if self.entity_description.key == "observed_rain_24h":
            attrs = {
                "unit_of_measurement": "mm",
                "status": data.observed_rain_status,
                "source": "Rachio WEATHER_INTELLIGENCE skip event text",
                "aggregation": "maximum observed_mm from skip events in the last 24h",
            }
            if data.observed_rain_best_event:
                attrs.update(data.observed_rain_best_event)
            return attrs
        if self.entity_description.key == "last_event":
            return {
                "last_event_at": data.last_event_at,
                "controller_name": data.controller_name,
                **_decision_compact_attrs(
                    label="Last event",
                    summary=data.last_event_summary,
                    at_local=_format_at_local(data.last_event_at),
                ),
            }
        if self.entity_description.key in {"last_run", "last_run_event"}:
            return {
                "last_run_at": data.last_run_at,
                "controller_name": data.controller_name,
                **_decision_compact_attrs(
                    label="Last run event" if self.entity_description.key == "last_run_event" else "Last run",
                    summary=data.last_run_summary,
                    at_local=_format_at_local(data.last_run_at),
                ),
            }
        if self.entity_description.key in {"last_skip", "last_skip_decision"}:
            return {
                "last_skip_at": data.last_skip_at,
                "controller_name": data.controller_name,
                **_decision_compact_attrs(
                    label="Last skip decision" if self.entity_description.key == "last_skip_decision" else "Last skip",
                    summary=data.last_skip_summary,
                    at_local=_format_at_local(data.last_skip_at),
                ),
            }
        if self.entity_description.key == "configured_zone_count":
            return {
                "expected_zone_count": data.zone_count,
                "discovered_schedule_count": data.active_schedule_count,
                "discovered_entities": data.discovered_entities,
            }
        if self.entity_description.key == "last_reconciliation":
            return {
                "supervisor_mode": data.supervisor_mode,
                "supervisor_reason": data.supervisor_reason,
                **_decision_compact_attrs(
                    label="Last reconciliation",
                    summary=data.last_reconciliation or "never",
                    at_local=_format_at_local(data.last_reconciliation),
                ),
            }
        if self.entity_description.key == "last_moisture_write":
            return {
                "last_moisture_write_at": data.last_moisture_write_at,
                "last_moisture_write_schedule": data.last_moisture_write_schedule,
                "last_moisture_write_value": data.last_moisture_write_value,
            }
        if self.entity_description.key == "ready_moisture_write_count":
            return {
                "moisture_write_queue": data.moisture_write_queue,
                "write_back_mode_enabled": data.action_posture.endswith("write_back_available"),
                "zero_state": data.recommended_moisture_write_count == 0
                and data.ready_moisture_write_count == 0,
                "moisture_review_items": list(data.moisture_review_items),
            }
        if self.entity_description.key == "moisture_write_queue":
            return {
                "ready_moisture_write_count": data.ready_moisture_write_count,
                "write_back_mode_enabled": data.action_posture.endswith("write_back_available"),
                "moisture_review_items": list(data.moisture_review_items),
            }
        if self.entity_description.key == "recommended_moisture_write_count":
            return {
                "recommended_moisture_write_queue": data.recommended_moisture_write_queue,
                "write_back_mode_enabled": data.action_posture.endswith("write_back_available"),
                "zero_state": data.recommended_moisture_write_count == 0
                and data.ready_moisture_write_count == 0,
                "moisture_review_items": list(data.moisture_review_items),
            }
        if self.entity_description.key == "recommended_moisture_write_queue":
            return {
                "recommended_moisture_write_count": data.recommended_moisture_write_count,
                "write_back_mode_enabled": data.action_posture.endswith("write_back_available"),
                "zero_state": data.recommended_moisture_write_count == 0
                and data.ready_moisture_write_count == 0,
                "moisture_review_items": list(data.moisture_review_items),
            }
        if self.entity_description.key == "active_recommendation_count":
            return {
                "active_recommendation_queue": data.active_recommendation_queue,
                "review_acknowledgements_persisted": False,
            }
        if self.entity_description.key == "active_recommendation_queue":
            return {
                "active_recommendation_count": data.active_recommendation_count,
                "review_acknowledgements_persisted": False,
            }
        if self.entity_description.key == "acknowledged_recommendation_count":
            return {
                "acknowledged_recommendation_queue": data.acknowledged_recommendation_queue,
                "review_acknowledgements_persisted": False,
            }
        if self.entity_description.key == "acknowledged_recommendation_queue":
            return {
                "acknowledged_recommendation_count": data.acknowledged_recommendation_count,
                "review_acknowledgements_persisted": False,
            }
        if self.entity_description.key == "catch_up_evidence":
            return {
                "reason": data.catch_up_evidence_reason,
                "schedule_name": data.catch_up_schedule_name,
                "runtime_minutes": data.catch_up_runtime_minutes,
                "summary": data.catch_up_summary,
                "decision_at": data.catch_up_decision_at,
            }
        if self.entity_description.key == "last_catch_up_decision":
            return {
                "reason": data.catch_up_evidence_reason,
                "schedule_name": data.catch_up_schedule_name,
                "runtime_minutes": data.catch_up_runtime_minutes,
                "summary": data.catch_up_summary,
                "decision_at": data.catch_up_decision_at,
                "subject": data.catch_up_schedule_name or "Catch-up monitor",
                "brief": (
                    f"ran {data.catch_up_runtime_minutes} min"
                    if data.catch_up_evidence_status == "executed"
                    else data.catch_up_evidence_status.replace("_", " ")
                ),
                "at_local": _format_at_local(data.catch_up_decision_at),
            }
        if self.entity_description.key in {
            "active_flow_alert_count",
            "flow_alert_queue",
            "last_flow_alert_decision",
        }:
            alerts = []
            if self.coordinator._cached_evidence is not None:
                alerts = [
                    {
                        "rule_id": alert.rule_id,
                        "zone_name": alert.zone_name,
                        "alert_kind": alert.alert_kind,
                        "alert_at": alert.alert_at,
                        "status": alert.status,
                        "reason": alert.reason,
                        "recommended_action": alert.recommended_action,
                        "baseline_before_lpm": alert.baseline_before_lpm,
                        "baseline_after_lpm": alert.baseline_after_lpm,
                        "baseline_delta_percent": alert.baseline_delta_percent,
                        "delta_percent": alert.baseline_delta_percent,
                        "calibration_at": alert.calibration_at,
                        "last_checked_at": data.last_reconciliation,
                        "review_state": alert.review_state,
                        "summary": alert.summary,
                    }
                    for alert in self.coordinator._cached_evidence.flow_alert_snapshots
                ]
            return {
                "active_flow_alert_count": data.active_flow_alert_count,
                "flow_alert_queue": data.flow_alert_queue,
                "last_flow_alert_decision": data.last_flow_alert_decision,
                "flow_alerts": alerts,
                "normal_tolerance_percent": 15,
                "native_calibration_api_available": False,
            }
        return None


class RachioSupervisorScheduleSensor(RachioSupervisorEntity, SensorEntity):
    """Per-schedule sensor entity."""

    def __init__(
        self,
        coordinator: RachioSupervisorCoordinator,
        schedule: ScheduleSnapshot,
        suffix: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._schedule_rule_id = schedule.rule_id
        self._suffix = suffix
        self._attr_name = f"{schedule.name} {label}"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{schedule.rule_id}_{suffix}"
        )

    def _current(self) -> ScheduleSnapshot | None:
        for schedule in self.coordinator.data.schedule_snapshots:
            if schedule.rule_id == self._schedule_rule_id:
                return schedule
        return None

    @property
    def native_value(self) -> str:
        """Return the current schedule value."""
        schedule = self._current()
        if schedule is None:
            return "unavailable"
        return str(getattr(schedule, self._suffix))

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Return contextual attributes for the current schedule sensor."""
        schedule = self._current()
        if schedule is None:
            return None
        return {
            "rule_id": schedule.rule_id,
            "schedule_name": schedule.name,
            "schedule_entity_id": schedule.schedule_entity_id,
            "zone_entity_id": schedule.zone_entity_id,
            "controller_zone_id": schedule.controller_zone_id,
            "policy_mode": schedule.policy_mode,
            "policy_basis": schedule.policy_basis,
            "moisture_entity_id": schedule.moisture_entity_id,
            "moisture_value": schedule.moisture_value,
            "moisture_status": schedule.moisture_status,
            "moisture_last_updated": schedule.moisture_last_updated,
            "sensor_value": schedule.moisture_value,
            "rachio_moisture_value": schedule.rachio_moisture_value or "not_reported",
            "write_value": schedule.write_value,
            "write_summary": schedule.write_summary,
            "auto_moisture_write_enabled": schedule.auto_moisture_write_enabled,
            "auto_moisture_write_status": schedule.auto_moisture_write_status,
            "last_moisture_write_status": schedule.last_moisture_write_status,
            "moisture_write_back_ready": schedule.moisture_write_back_ready,
            "recommended_action": schedule.recommended_action,
            "review_state": schedule.review_state,
            "review_acknowledgements_persisted": False,
            "runtime_minutes": schedule.runtime_minutes,
            "last_run_at": schedule.last_run_at,
            "last_skip_at": schedule.last_skip_at,
            "observed_mm": schedule.observed_mm,
            "threshold_mm": schedule.threshold_mm,
            "summary": schedule.summary,
        }
