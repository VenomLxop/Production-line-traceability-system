"""The recall query -- the killer feature.

Given a unit_id, return its full trace in one query. Given a batch_id,
return every unit made from it (the actual recall scenario: "batch 003 had
a bad component, which units shipped with it?").

Both queries lean on the indexes defined in traceability/models.py
(ix_station_events_unit_id, ix_units_batch_id) so they stay sub-second even
as the events table grows into the millions of rows.

CLI usage:
    python -m recall.query unit UNIT-ABC123
    python -m recall.query batch BATCH-003
"""
import argparse
import sys

from sqlalchemy.orm import Session

from traceability.db import SessionLocal
from traceability.models import StationEvent, Unit


def get_unit_trace(session: Session, unit_id: str) -> dict | None:
    """Full trace for one unit: its batch and every station event, ordered."""
    unit = session.get(Unit, unit_id)
    if unit is None:
        return None

    events = (
        session.query(StationEvent)
        .filter(StationEvent.unit_id == unit_id)
        .order_by(StationEvent.timestamp)
        .all()
    )

    return {
        "unit_id": unit.unit_id,
        "batch_id": unit.batch_id,
        "material_source": unit.batch.material_source if unit.batch else None,
        "created_at": unit.created_at,
        "events": [
            {
                "station": e.station,
                "timestamp": e.timestamp,
                "operator": e.operator,
                "cycle_time": e.cycle_time,
                "temperature": e.temperature,
                "pass_fail": e.pass_fail,
                "reconciled": e.reconciled,
            }
            for e in events
        ],
    }


def get_units_by_batch(session: Session, batch_id: str) -> list[str]:
    """Every unit made from a given batch -- the recall list."""
    rows = session.query(Unit.unit_id).filter(Unit.batch_id == batch_id).all()
    return [r[0] for r in rows]


def _print_trace(trace: dict) -> None:
    print(f"Unit:     {trace['unit_id']}")
    print(f"Batch:    {trace['batch_id']} ({trace['material_source']})")
    print(f"Created:  {trace['created_at']}")
    print("Events:")
    for e in trace["events"]:
        flag = " [RECONCILED]" if e["reconciled"] else ""
        print(
            f"  {e['station']:>8} | {e['timestamp']} | op={e['operator']} | "
            f"cycle={e['cycle_time']}s | temp={e['temperature']}C | "
            f"{e['pass_fail']}{flag}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Recall query CLI")
    parser.add_argument("kind", choices=["unit", "batch"])
    parser.add_argument("value")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.kind == "unit":
            trace = get_unit_trace(session, args.value)
            if trace is None:
                print(f"No unit found with id {args.value}")
                sys.exit(1)
            _print_trace(trace)
        else:
            units = get_units_by_batch(session, args.value)
            print(f"Batch {args.value}: {len(units)} unit(s)")
            for uid in units:
                print(f"  {uid}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
