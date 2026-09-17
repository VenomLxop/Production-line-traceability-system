"""The integrity layer: a set of checks that run against the ingested data
to find gaps in traceability, plus the daily completeness score.

STATIONS defines the expected order a unit should pass through the line.
Every check here is a plain SQLAlchemy query -- no magic, so it's easy to
walk through in an interview.
"""
from collections import defaultdict
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from traceability.models import DailyScore, StationEvent, Unit

STATIONS = ["assembly", "test", "pack"]


def missing_scans(session: Session) -> dict[str, list[str]]:
    """For each station, which units have an earlier-station event but no
    event at this station at all. Returns {station: [unit_id, ...]}."""
    all_units = [u.unit_id for u in session.query(Unit.unit_id).all()]
    events_by_unit: dict[str, set[str]] = defaultdict(set)
    for unit_id, station in session.query(StationEvent.unit_id, StationEvent.station).all():
        events_by_unit[unit_id].add(station)

    missing: dict[str, list[str]] = {station: [] for station in STATIONS}
    for unit_id in all_units:
        seen = events_by_unit.get(unit_id, set())
        for i, station in enumerate(STATIONS):
            # Only flag a station as "missing" if the unit made it past the
            # stations before it -- otherwise it's simply still in progress.
            reached_here_or_later = any(s in seen for s in STATIONS[i:])
            if station not in seen and reached_here_or_later:
                missing[station].append(unit_id)
    return missing


def out_of_order_events(session: Session) -> list[dict]:
    """Units whose station timestamps are not monotonically increasing in
    the expected assembly -> test -> pack order."""
    rows = session.query(
        StationEvent.unit_id, StationEvent.station, StationEvent.timestamp
    ).all()

    timestamps_by_unit: dict[str, dict[str, datetime]] = defaultdict(dict)
    for unit_id, station, ts in rows:
        timestamps_by_unit[unit_id][station] = ts

    violations = []
    for unit_id, by_station in timestamps_by_unit.items():
        ordered = [by_station[s] for s in STATIONS if s in by_station]
        if ordered != sorted(ordered):
            violations.append(
                {"unit_id": unit_id, "timestamps": {s: by_station[s] for s in by_station}}
            )
    return violations


def duplicate_scans(session: Session) -> list[dict]:
    """Same unit_id + station scanned more than once."""
    rows = (
        session.query(StationEvent.unit_id, StationEvent.station, func.count().label("n"))
        .group_by(StationEvent.unit_id, StationEvent.station)
        .having(func.count() > 1)
        .all()
    )
    return [{"unit_id": r[0], "station": r[1], "count": r[2]} for r in rows]


def orphaned_units(session: Session) -> list[str]:
    """station_events rows whose unit_id has no corresponding units row."""
    known_units = {u.unit_id for u in session.query(Unit.unit_id).all()}
    all_event_unit_ids = {r[0] for r in session.query(StationEvent.unit_id).distinct().all()}
    return sorted(all_event_unit_ids - known_units)


def units_created_on(session: Session, day: str) -> list[Unit]:
    """day is 'YYYY-MM-DD'."""
    return (
        session.query(Unit)
        .filter(func.strftime("%Y-%m-%d", Unit.created_at) == day)
        .all()
    )


def is_unit_complete_and_ordered(session: Session, unit_id: str) -> bool:
    """A unit counts as fully traceable if it has exactly one event at each
    station and those events are in the correct chronological order."""
    events = (
        session.query(StationEvent.station, StationEvent.timestamp)
        .filter(StationEvent.unit_id == unit_id)
        .all()
    )
    by_station = {station: ts for station, ts in events}
    if set(by_station.keys()) != set(STATIONS):
        return False
    ordered = [by_station[s] for s in STATIONS]
    return ordered == sorted(ordered)


def compute_daily_completeness(session: Session, day: str) -> DailyScore:
    """Completeness = (units with all 3 station events, present & in order)
    / (total units created that day). Persists the result to daily_scores."""
    units = units_created_on(session, day)
    total = len(units)
    complete = sum(1 for u in units if is_unit_complete_and_ordered(session, u.unit_id))
    score = (complete / total) if total else 0.0

    record = DailyScore(
        score_date=day,
        total_units=total,
        complete_units=complete,
        score=score,
    )
    session.add(record)
    session.commit()
    return record


def run_all_checks(session: Session) -> dict:
    """Convenience bundle used by the report script."""
    return {
        "missing_scans": missing_scans(session),
        "out_of_order": out_of_order_events(session),
        "duplicates": duplicate_scans(session),
        "orphaned": orphaned_units(session),
    }
