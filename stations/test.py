"""Test station simulator.

Subscribes to Assembly's topic (its "unit arrived" signal), simulates a
test cycle for each unit, and publishes a Test-station event.

DELIBERATE DEFECT: ~4% of units are silently dropped here and never
published, simulating a flaky sensor/network link on this station only.
This is intentional -- the integrity layer (integrity/checks.py) is built
to catch exactly this kind of gap.

Run: python -m stations.test
"""
import json
import random
import time

from traceability.config import TEST_STATION_DROP_RATE, TOPIC_ASSEMBLY, TOPIC_TEST
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

    if random.random() < TEST_STATION_DROP_RATE:
        # The scan never made it off the station -- no event is published,
        # no trace of it exists anywhere except this log line.
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
