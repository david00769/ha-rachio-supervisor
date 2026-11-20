"""Read-only projections of Rachio's documented 14-day upcoming runs."""

from __future__ import annotations

import math
from datetime import datetime


class InvalidUpcomingRuns(ValueError):
    """The vendor forecast failed structural or value validation."""


def run_datetime(value: object) -> datetime | None:
    """Accept only timezone-aware vendor timestamps, preserving controller offsets."""
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value)
    except ValueError:
        return None
    return result if result.utcoffset() is not None else None


def positive_seconds(value: object) -> float | None:
    """Reject missing, boolean, nonfinite or nonpositive durations."""
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def normalize_upcoming_runs(payload: object) -> tuple[dict[str, object], ...]:
    """Validate the API response without fabricating schedule dates or skip durations.

    Fail the complete optional report on malformed data so a partial response is
    never presented as an authoritative empty or complete calendar.
    """
    if not isinstance(payload, list):
        raise InvalidUpcomingRuns("Upcoming runs response must be a list")
    runs = []
    for raw in payload:
        if not isinstance(raw, dict):
            raise InvalidUpcomingRuns("Upcoming run must be an object")
        start = run_datetime(raw.get("startTime"))
        end = run_datetime(raw.get("endTime"))
        if start is None or end is None or end < start:
            raise InvalidUpcomingRuns(
                "Upcoming run requires ordered, timezone-aware timestamps"
            )
        rule_id = raw.get("scheduleRuleId")
        if not isinstance(rule_id, str) or not rule_id:
            raise InvalidUpcomingRuns("Upcoming run requires a schedule id")
        skipped = raw.get("skipped")
        if not isinstance(skipped, bool):
            raise InvalidUpcomingRuns("Upcoming run requires a skipped flag")
        zones = []
        if not skipped:
            raw_zones = raw.get("zones")
            if not isinstance(raw_zones, list):
                raise InvalidUpcomingRuns("Upcoming run requires a zone list")
            for zone in raw_zones:
                if not isinstance(zone, dict) or not zone.get("zoneId"):
                    raise InvalidUpcomingRuns("Upcoming zone requires a zone id")
                duration = positive_seconds(zone.get("duration"))
                if duration is None:
                    raise InvalidUpcomingRuns(
                        "Upcoming zone requires a positive duration"
                    )
                zones.append(
                    {
                        "zone_id": str(zone["zoneId"]),
                        "zone_number": zone.get("zoneNumber"),
                        "zone_name": str(zone.get("zoneName") or zone["zoneId"]),
                        "duration_seconds": duration,
                    }
                )
        runs.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "schedule_id": rule_id,
                "schedule_name": str(raw.get("scheduleName") or rule_id),
                "skipped": skipped,
                "skip_cause": str(raw.get("skipCause") or "unspecified")
                if skipped
                else None,
                "cycle_soak": bool(raw.get("cycleSoak")) if not skipped else None,
                "watering_seconds": positive_seconds(raw.get("totalDuration"))
                if not skipped
                else None,
                "elapsed_seconds": (end - start).total_seconds(),
                "zones": zones,
            }
        )
    runs.sort(key=lambda run: run_datetime(run["start"]))
    return tuple(runs)
