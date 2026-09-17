"""Test station simulator.

Subscribes to Assembly's topic (its "unit arrived" signal), simulates a
test cycle for each unit, and publishes a Test-station event.

DELIBERATE DEFECT: ~4% of units have their Test scan *event* silently
dropped and never published to TOPIC_TEST, simulating a flaky
sensor/network link on this station only. This is intentional -- the
integrity layer (integrity/checks.py) is built to catch exactly this kind
of gap.

Note this only drops the data point, not the physical unit: a
lightweight "advance" signal is always published on TOPIC_TEST_ADVANCE so
Pack still receives every unit, exactly as a real conveyor would keep
moving a unit whose scan failed to register. That's what makes the gap
show up as "has Assembly and Pack, missing Test" rather than the unit
vanishing from the line entirely.

Run: python -m stations.test
"""
import json
import random
import time

from traceability.config import (
    TEST_STATION_DROP_RATE,
    TOPIC_ASSEMBLY,
    TOPIC_TEST,
    TOPIC_TEST_ADVANCE,
)
from stations.common import build_event, make_client, publish_event

dropped_count = 0
processed_count = 0


def on_message(client, userdata, msg):
    global dropped_count, processed_count
    incoming = json.loads(msg.payload.decode())
    unit_id = incoming["unit_id"]
    batch_id = incoming["batch_id"]

    # Simulate the physical test cycle taking a moment.
    time.sleep(random.uniform(0.3, 1.2))

    # The physical unit always advances to Pack...
    publish_event(client, TOPIC_TEST_ADVANCE, {"unit_id": unit_id, "batch_id": batch_id})

    if random.random() < TEST_STATION_DROP_RATE:
        # ...but its scan event can still be lost, e.g. a sensor/network
        # fault. No row for this station ever reaches the database.
        dropped_count += 1
        print(f"[test] {unit_id} -- SCAN DROPPED (simulated sensor fault)")
        return

    event = build_event(unit_id, batch_id, station="test")
    publish_event(client, TOPIC_TEST, event)
    processed_count += 1
    print(f"[test] {unit_id} -> published ({processed_count} ok, {dropped_count} dropped)")


def run() -> None:
    client = make_client("station-test")
    client.on_message = on_message
    client.subscribe(TOPIC_ASSEMBLY, qos=1)

    print("[test] station online, listening for units from assembly...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        print(f"[test] shutting down, {processed_count} processed, {dropped_count} dropped")


if __name__ == "__main__":
    run()
