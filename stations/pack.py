"""Pack station simulator.

Subscribes to the Test station's "advance" signal (published for every
unit that physically leaves Test, whether or not its scan event survived
-- see stations/test.py) and publishes a Pack-station event for each one.
This means a unit whose Test scan was dropped still reaches Pack, so it
shows up in the data as "has Assembly and Pack, missing Test" -- exactly
the kind of gap the integrity layer is designed to detect.

Run: python -m stations.pack
"""
import json
import random
import time

from traceability.config import TOPIC_PACK, TOPIC_TEST_ADVANCE
from stations.common import build_event, make_client, publish_event

processed_count = 0


def on_message(client, userdata, msg):
    global processed_count
    incoming = json.loads(msg.payload.decode())
    unit_id = incoming["unit_id"]
    batch_id = incoming["batch_id"]

    time.sleep(random.uniform(0.3, 1.0))

    event = build_event(unit_id, batch_id, station="pack")
    publish_event(client, TOPIC_PACK, event)
    processed_count += 1
    print(f"[pack] {unit_id} -> published ({processed_count} total)")


def run() -> None:
    client = make_client("station-pack")
    client.on_message = on_message
    client.subscribe(TOPIC_TEST_ADVANCE, qos=1)

    print("[pack] station online, listening for units from test...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        print(f"[pack] shutting down, {processed_count} processed")


if __name__ == "__main__":
    run()
