# Milestones

| Milestone | Planned | Actual | Notes |
|---|---|---|---|
| Repo scaffold + plan agreed | Day 1 | Day 1 | Structure settled quickly: shared `traceability/` package for config/DB/models, one folder per pipeline stage. |
| Station simulators (assembly/test/pack) | Day 1 | Day 2 | Slipped a day -- decided mid-build to chain stations via MQTT subscription (station N+1 listens to station N) instead of having each station generate its own units, since that's what makes the line behave like a real one and makes the Test-station drop actually propagate downstream. |
| MQTT broker + ingest service | Day 2 | Day 2 | `paho-mqtt` 2.x shipped a breaking API change (`callback_api_version` now required) since the original plan was written against 1.6.x; caught during first local smoke test, one-line fix per client. |
| Integrity layer + injected 4% Test-station drop | Day 2-3 | Day 3 | Core deliverable, took the most iteration. Settled on "missing scan" meaning *reached a later station but skipped this one* rather than any incomplete unit, so units still in flight aren't false-flagged. |
| Reconciliation fix + honest audit trail | Day 3 | Day 3 | Backfilled Test events are timestamp-interpolated between Assembly and Pack and explicitly marked `reconciled=True` / operator `MANUAL-RECONCILE` -- no silent data fabrication. |
| Recall query (unit + batch lookup) | Day 3 | Day 3 | On schedule. Added indexes on `unit_id` and `batch_id` up front rather than as an afterthought, since "sub-second" was a stated requirement. |
| Streamlit dashboard | Day 4 | Day 4 | On schedule. |
| TPM docs (README, ARCHITECTURE, MILESTONES, RAID) | Day 4 | Day 4-5 | Slipped slightly -- wrote these last, after running the full simulation end-to-end, so the post-mortem numbers in the README are real output from a local run rather than invented figures. |

*Dates are relative (Day 1-5), not calendar dates, since this was built in a single continuous session -- the point of the table is to show the honest order and friction of the work, not a fictional clean plan.*
