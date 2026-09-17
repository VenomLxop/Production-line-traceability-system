"""Assembly station simulator.

Head of the line: creates a brand-new unit (unique unit_id + a batch_id
drawn from the raw-material batch pool), "scans" it at Assembly, and
publishes the event. Downstream stations (test.py, pack.py) each subscribe
to the station before them, so this is the only process that originates
units.

Run: python -m stations.assembly
"""
import random
import sys
import uuid

from traceability.config import BATCH_POOL, TOPIC_ASSEMBLY
from stations.common import build_event, make_client, publish_event, sleep_between_units


def run(unit_limit: int | None = None) -> None:
    client = make_client("station-assembly")
    client.loop_start()

    produced = 0
    print("[assembly] station online, producing units...")
    try:
        while unit_limit is None or produced < unit_limit:
            unit_id = f"UNIT-{uuid.uuid4().hex[:10].upper()}"
            batch_id = random.choice(BATCH_POOL)

            event = build_event(unit_id, batch_id, station="assembly")
            publish_event(client, TOPIC_ASSEMBLY, event)
            print(f"[assembly] {unit_id} (batch={batch_id}) -> published")

            produced += 1
            sleep_between_units(min_s=1.0, max_s=3.0)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"[assembly] shutting down, {produced} units produced")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run(unit_limit=limit)
