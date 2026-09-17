"""Prints a traceability integrity report, quantifies the impact of the
Test-station scan drop, applies the reconciliation fix, and recomputes the
score so you can see the before/after in one run.

Run: python -m integrity.report [--fix] [--day YYYY-MM-DD]
"""
import argparse
from datetime import datetime, timezone

from traceability.db import SessionLocal, init_db
from traceability.models import Unit
from integrity.checks import compute_daily_completeness, run_all_checks
from integrity.reconcile import reconcile_missing_test_scans


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def print_report(session, day: str) -> None:
    checks = run_all_checks(session)
    total_units = session.query(Unit).count()

    print("=" * 60)
    print(f"TRACEABILITY INTEGRITY REPORT -- {day}")
    print("=" * 60)

    print(f"\nTotal units in system: {total_units}")

    print("\n-- Missing scans --")
    for station, units in checks["missing_scans"].items():
        pct = (len(units) / total_units * 100) if total_units else 0.0
        print(f"  {station:>8}: {len(units)} units missing ({pct:.1f}%)")

    print(f"\n-- Out-of-order events: {len(checks['out_of_order'])} unit(s) --")
    for v in checks["out_of_order"][:5]:
        print(f"  {v['unit_id']}: {v['timestamps']}")

    print(f"\n-- Duplicate scans: {len(checks['duplicates'])} row(s) --")
    for d in checks["duplicates"][:5]:
        print(f"  {d['unit_id']} @ {d['station']}: scanned {d['count']}x")

    print(f"\n-- Orphaned station_events: {len(checks['orphaned'])} unit_id(s) --")
    for uid in checks["orphaned"][:5]:
        print(f"  {uid}")

    score = compute_daily_completeness(session, day)
    missing_test_pct = (
        len(checks["missing_scans"]["test"]) / total_units * 100 if total_units else 0.0
    )
    print(f"\n-- Completeness score for {day} --")
    print(
        f"  {score.complete_units}/{score.total_units} units fully traced "
        f"-> {score.score * 100:.1f}%"
    )
    print(
        f"  Completeness score: {score.score * 100:.1f}% -- driven by "
        f"{missing_test_pct:.1f}% missing Test scans"
    )


def apply_fix(session, day: str) -> None:
    print("\n" + "=" * 60)
    print("APPLYING FIX: reconciling units with missing Test scans")
    print("=" * 60)
    reconciled = reconcile_missing_test_scans(session)
    print(f"  Backfilled Test events for {len(reconciled)} unit(s), "
          f"marked reconciled=True")

    score_after = compute_daily_completeness(session, day)
    print(f"\n-- Completeness score for {day} AFTER fix --")
    print(
        f"  {score_after.complete_units}/{score_after.total_units} units fully traced "
        f"-> {score_after.score * 100:.1f}%"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Traceability integrity report")
    parser.add_argument("--fix", action="store_true", help="apply reconciliation after report")
    parser.add_argument("--day", default=today(), help="YYYY-MM-DD, defaults to today (UTC)")
    args = parser.parse_args()

    init_db()
    session = SessionLocal()
    try:
        print_report(session, args.day)
        if args.fix:
            apply_fix(session, args.day)
    finally:
        session.close()


if __name__ == "__main__":
    main()
