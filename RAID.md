# RAID Log

## Risks

- **MQTT broker is a single point of failure.** Every station and the
  ingest service depend on one Mosquitto instance; if it goes down, no
  events flow and nothing is persisted (not even a partial local buffer).
  Mitigation for a real deployment: broker clustering or at least a
  supervised restart; out of scope for this sim.
- **SQLite under concurrent writes.** The ingest service is the only
  writer today, but if a second writer were added (e.g. the reconciliation
  script running while ingest is live) SQLite's file-level locking could
  cause contention. Low risk at this scale, real risk if this ever needs
  to run at production line throughput.
- **Silent data loss looks identical to "unit still in progress."** The
  integrity checks distinguish these by whether the unit reached a later
  station, but a unit that's simply slow (still at Test, hasn't reached
  Pack yet) could theoretically be confused with one that's stuck, if a
  check were run mid-shift. Mitigated by running completeness checks
  end-of-day rather than continuously.

## Assumptions

- A unit is created exactly once, at Assembly, and flows through exactly
  the three stations in order. No rework loops, no parallel lines, no
  unit skipping a station on purpose.
- Clocks across all processes are in sync (all running on one host in this
  sim), so timestamp-ordering checks are meaningful. A real multi-machine
  deployment would need NTP-synced clocks or logical clocks.
- One batch = one raw-material lot, and a unit belongs to exactly one
  batch. No sub-assemblies with their own independent genealogy.

## Issues

- **4% of Test-station scans are lost** (discovered because it was
  deliberately injected for this exercise, but modeled on real
  sensor/network flakiness). Caught by the completeness score and the
  `missing_scans` check; see the README post-mortem for the full story and
  the fix.
- **`paho-mqtt` 2.x is a breaking change from 1.x** (`Client()` now
  requires an explicit `callback_api_version`). Found during the first
  local end-to-end smoke test; fixed by pinning to `CallbackAPIVersion.VERSION1`
  everywhere a client is constructed, and loosening the requirements.txt
  pin so the fix doesn't silently regress.

## Dependencies

- **Mosquitto** (via docker-compose) -- the only external service the
  system depends on.
- **paho-mqtt, SQLAlchemy, Streamlit, pandas** -- all pure-Python, no
  other services required.
- **Local Docker** for the broker. If Docker isn't available, any local
  Mosquitto install works too (`docker-compose.yml` just wraps
  `mosquitto/config/mosquitto.conf`, which can be pointed at a
  natively-installed broker instead).
