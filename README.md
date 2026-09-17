# line-traceability-sim

A local, hardware-free simulation of a 3-station production line
(**Assembly → Test → Pack**) built to demonstrate manufacturing
traceability: unique unit IDs scanned at every station, an integrity layer
that catches gaps in that scan history, and a fast recall query for "which
units does this affect?"

It's a simulation you can run entirely on a laptop: no real scanners, no
Grafana stack, no Kubernetes -- three Python processes standing in for
stations, one MQTT broker, one SQLite database, one Streamlit dashboard.

## Overview

- **Stations** (`stations/assembly.py`, `test.py`, `pack.py`) are separate
  Python processes. Assembly creates a new unit (unique `unit_id` + a
  `batch_id` from a small raw-material batch pool) and publishes a scan
  event over MQTT. Test subscribes to Assembly's events, and Pack
  subscribes to a "unit physically left Test" signal that Test always
  sends -- so every unit reaches Pack, just like a real conveyor, even if
  its Test *scan data* didn't make it.
- **Test station drops ~4% of scan events on purpose** (not the physical
  units themselves). This is a deliberately injected defect simulating a
  flaky sensor/network link, so the integrity layer below has something
  real to catch. See the post-mortem.
- **Ingest service** (`ingest/ingest_service.py`) subscribes to every
  station's topic and writes rows into SQLite via SQLAlchemy.
- **Integrity layer** (`integrity/`) runs checks (missing scans,
  out-of-order events, duplicate scans, orphaned units) and computes a
  daily traceability completeness score.
- **Reconciliation** (`integrity/reconcile.py`) backfills a plausible Test
  event for units it flags, honestly marked `reconciled=True` in the DB.
- **Recall query** (`recall/query.py`) answers "what's the full trace of
  this unit?" and "what units came from this batch?" in one indexed query.
- **Dashboard** (`dashboard/app.py`, Streamlit) shows throughput, yield,
  cycle time, the completeness score over time, and a recall search box.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and data model.

```
assembly.py --MQTT--> test.py (drops ~4%) --MQTT--> pack.py
      \___________________|___________________/
                          |
                    ingest_service.py
                          |
                   SQLite (units, batches,
                   station_events, daily_scores)
                          |
              integrity layer  <->  dashboard / recall query
```

## How to run it

### 1. Start the MQTT broker

```bash
docker-compose up -d
```

(If Docker isn't available, any local Mosquitto broker listening on
`localhost:1883` with anonymous access works -- point it at
`mosquitto/config/mosquitto.conf`.)

### 2. Install dependencies

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the line

```bash
./scripts/run_line.sh          # runs indefinitely, Ctrl+C to stop
./scripts/run_line.sh 200      # stops assembly after 200 units
```

This starts the ingest service and all three stations as background
processes and writes their logs to `./logs/`. Or run each process manually
in its own terminal for a clearer view of what's happening:

```bash
python -m ingest.ingest_service
python -m stations.pack
python -m stations.test
python -m stations.assembly
```

### 4. Run the integrity report

```bash
python -m integrity.report          # report only
python -m integrity.report --fix    # report, then reconcile + rescore
```

### 5. Try the recall query

```bash
python -m recall.query unit UNIT-XXXXXXXXXX
python -m recall.query batch BATCH-003
```

### 6. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

## Post-mortem: the 4% Test-station scan loss

**What broke.** During the first full end-to-end run of the line (200
units through Assembly), the traceability completeness score came back
below the 95% target. `integrity.report` pointed straight at it:

```
-- Missing scans --
  assembly: 0 units missing (0.0%)
      test: 9 units missing (4.5%)
      pack: 0 units missing (0.0%)

-- Completeness score for 2026-09-17 --
  191/200 units fully traced -> 95.5%
  Completeness score: 95.5% -- driven by 4.5% missing Test scans
```

*(These are real numbers from a local run of this repo, not invented
figures -- run `python -m integrity.report` yourself and you'll get a
similarly-shaped result, since the drop rate is randomized per run.)*

The physical unit still reaches Pack even when its Test scan is lost --
Test always signals "this unit physically moved on" to Pack independently
of whether its own scan event made it into the database (see
`stations/test.py` / `stations/pack.py`). That's deliberate: it's what
makes the gap show up correctly as "has Assembly and Pack, missing Test"
rather than the unit silently disappearing from the line's records
altogether, which is the more insidious version of this failure -- a
station's sensor fault costing you a specific, attributable data point
that traces back to exactly this station, not an unexplained hole in the
whole downstream trace.

**How the integrity layer caught it.** `integrity.checks.missing_scans`
flags any unit that reached a *later* station but has no event at an
earlier one it should have passed through -- so it correctly ignored units
that were simply still in flight, and correctly flagged the 9 units Test
actually dropped (and only those). The daily completeness score
(`compute_daily_completeness`) turned that into a single number a shift
lead could act on without reading raw logs, and the orphaned/duplicate/
out-of-order checks all came back empty, confirming the *rest* of the
pipeline was clean -- this wasn't a broader ingest bug, it was isolated to
the one station.

**The fix.** `integrity.reconcile.reconcile_missing_test_scans` finds every
unit flagged as missing its Test scan, and -- since we know it has both an
Assembly and a Pack timestamp -- backfills a Test event interpolated
between the two. Critically, that backfilled row is marked
`reconciled=True` with operator `MANUAL-RECONCILE`, so the audit trail
never pretends a manual fix was a real sensor reading -- `recall.query`
shows a `[RECONCILED]` flag next to any backfilled event. In production
this reconciliation step would be a manual QA task (re-scan the physical
unit or confirm it visually), not an automated backfill -- the script
here simulates that outcome so the before/after is demonstrable
end-to-end:

```
============================================================
APPLYING FIX: reconciling units with missing Test scans
============================================================
  Backfilled Test events for 9 unit(s), marked reconciled=True

-- Completeness score for 2026-09-17 AFTER fix --
  200/200 units fully traced -> 100.0%
```

Completeness recovered from 95.5% to 100.0%, and all 9 reconciled units
are queryable via `recall.query unit <id>` with their `[RECONCILED]` flag
intact -- the fix closes the traceability gap without hiding that a fix
was applied.

## TPM artifacts

- [MILESTONES.md](MILESTONES.md) -- planned vs. actual, including the
  slips
- [RAID.md](RAID.md) -- risks, assumptions, issues, dependencies
- [ARCHITECTURE.md](ARCHITECTURE.md) -- full diagram and data model

## Tech stack

Python 3.11, `paho-mqtt`, SQLAlchemy + SQLite, Streamlit, docker-compose
(Mosquitto only).
