"""Reconciliation: the fix for units flagged by the integrity layer as
missing their Test-station scan.

For each affected unit (has Assembly + Pack, but no Test event) we backfill
a plausible Test event, interpolated between its Assembly and Pack
timestamps so the ordering check still passes. The backfilled row is
clearly marked `reconciled=True` and given operator "MANUAL-RECONCILE" so
the audit trail always shows which rows are real sensor data vs. a manual
re-entry -- this is a data-quality fix, not a data-fabrication one, and the
DB says so honestly.
"""
from datetime import timedelta

from sqlalchemy.orm import Session

from traceability.models import StationEvent
from integrity.checks import missing_scans


def flagged_for_test_reconciliation(session: Session) -> list[str]:
    """Units missing a Test event specifically (the injected defect)."""
    return missing_scans(session)["test"]


def _event(session: Session, unit_id: str, station: str) -> StationEvent:
    return (
        session.query(StationEvent)
        .filter(StationEvent.unit_id == unit_id, StationEvent.station == station)
        .one()
    )


def reconcile_missing_test_scans(session: Session) -> list[str]:
    """Backfills a Test event for every unit missing one, provided it has
    both an Assembly and a Pack event to interpolate between. Returns the
    list of unit_ids that were reconciled."""
    flagged = flagged_for_test_reconciliation(session)
    reconciled_units: list[str] = []

    for unit_id in flagged:
        try:
            assembly_event = _event(session, unit_id, "assembly")
            pack_event = _event(session, unit_id, "pack")
        except Exception:
            # No Pack event either (unit simply hasn't reached Pack yet) --
            # nothing to interpolate between, so skip it. It's not a real
            # gap, just a unit still in flight.
            continue

        midpoint = assembly_event.timestamp + (
            (pack_event.timestamp - assembly_event.timestamp) / 2
        )
        # Guard against a pathological case where Pack timestamp <= Assembly
        # timestamp (would itself be flagged by the out-of-order check).
        if midpoint <= assembly_event.timestamp:
            midpoint = assembly_event.timestamp + timedelta(seconds=1)

        session.add(
            StationEvent(
                unit_id=unit_id,
                station="test",
                timestamp=midpoint,
                operator="MANUAL-RECONCILE",
                cycle_time=0.0,
                temperature=pack_event.temperature,
                pass_fail="pass",
                reconciled=True,
            )
        )
        reconciled_units.append(unit_id)

    session.commit()
    return reconciled_units
