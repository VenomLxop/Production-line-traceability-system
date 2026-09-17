"""Central configuration for the line-traceability-sim project.

Everything reads from environment variables with sane local defaults so the
whole system can be run with plain `python` processes plus a single
dockerized Mosquitto broker.
"""
import os

# --- MQTT ---
MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# Topics form a chain: assembly -> test -> pack. Each station simulator
# subscribes to the previous station's topic (its "unit arrived" signal)
# and publishes to its own "*/events" topic when it finishes processing a
# unit -- these events topics are what the ingest service records.
#
# TOPIC_TEST_ADVANCE is separate on purpose: a physical unit still moves
# on to Pack even if its Test scan event is dropped (a flaky sensor loses
# the *data point*, it doesn't stop the conveyor). So Pack subscribes to
# this always-published "unit physically left Test" signal rather than to
# TOPIC_TEST itself -- otherwise a dropped Test scan would also silently
# swallow the unit's Pack scan, and the integrity layer would never see
# the gap it's meant to catch.
TOPIC_ASSEMBLY = "line/assembly/events"
TOPIC_TEST = "line/test/events"
TOPIC_TEST_ADVANCE = "line/test/advance"
TOPIC_PACK = "line/pack/events"
TOPIC_ALL_EVENTS = "line/+/events"

# --- Database ---
# SQLite by default. Swapping to Postgres later is a one-line change here
# because everything downstream goes through SQLAlchemy.
DB_URL = os.environ.get("DB_URL", "sqlite:///traceability.db")

# --- Simulation knobs ---
BATCH_POOL = [f"BATCH-{n:03d}" for n in range(1, 6)]
MATERIAL_SOURCES = {
    "BATCH-001": "Supplier A - Steel Housing Lot 44",
    "BATCH-002": "Supplier A - Steel Housing Lot 45",
    "BATCH-003": "Supplier B - Steel Housing Lot 12",
    "BATCH-004": "Supplier C - Polymer Casing Lot 7",
    "BATCH-005": "Supplier C - Polymer Casing Lot 8",
}
OPERATOR_POOL = ["OP-101", "OP-102", "OP-103", "OP-104", "OP-105"]

# Deliberate defect injection: fraction of Test-station scans dropped
# entirely (never published), simulating a flaky sensor/network link.
TEST_STATION_DROP_RATE = 0.04

# Dashboard alerting threshold for the traceability completeness score.
COMPLETENESS_TARGET = 0.95
