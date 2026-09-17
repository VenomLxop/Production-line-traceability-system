"""Ingest service.

Subscribes to every station's event topic and writes rows into SQLite via
SQLAlchemy. This is the only process that writes to station_events/units/
batches, so there's no write contention to worry about.

- On an "assembly" event: upsert the Batch row and create the Unit row
  (this is the unit's first appearance in the system).
- On every event: insert a StationEvent row.

Run: python -m ingest.ingest_service
"""
import json
from datetime import datetime

from traceability.config import MATERIAL_SOURCES, MQTT_HOST, MQTT_PORT, TOPIC_ALL_EVENTS
from traceability.db import SessionLocal, init_db
from traceability.models import Batch, StationEvent, Unit

import paho.mqtt.client as mqtt

event_count = 0


def _ensure_batch(session, batch_id: str) -> None:
    if session.get(Batch, batch_id) is None:
        session.add(
            Batch(
                batch_id=batch_id,
                material_source=MATERIAL_SOURCES.get(batch_id, "Unknown source"),
            )
        )


def _ensure_unit(session, unit_id: str, batch_id: str, created_at: datetime) -> None:
    if session.get(Unit, unit_id) is None:
        session.add(Unit(unit_id=unit_id, batch_id=batch_id, created_at=created_at))


def handle_event(session, payload: dict) -> None:
    global event_count
    timestamp = datetime.fromisoformat(payload["timestamp"])

    # A unit only "exists" in the units table once it has passed Assembly.
    # (In this sim that's always the first event we see for a unit_id,
    # since Assembly originates every unit.)
    if payload["station"] == "assembly":
        _ensure_batch(session, payload["batch_id"])
        _ensure_unit(session, payload["unit_id"], payload["batch_id"], timestamp)

    session.add(
        StationEvent(
            unit_id=payload["unit_id"],
            station=payload["station"],
            timestamp=timestamp,
            operator=payload["operator"],
            cycle_time=payload["cycle_time"],
            temperature=payload["temperature"],
            pass_fail=payload["pass_fail"],
        )
    )
    session.commit()
    event_count += 1


def on_message(client, userdata, msg):
    session = userdata
    payload = json.loads(msg.payload.decode())
    handle_event(session, payload)
    print(f"[ingest] {payload['station']:>8} <- {payload['unit_id']} (total={event_count})")


def run() -> None:
    init_db()
    session = SessionLocal()

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id="ingest-service",
        clean_session=True,
        userdata=session,
    )
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.subscribe(TOPIC_ALL_EVENTS, qos=1)

    print("[ingest] online, writing station events to the database...")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        session.close()
        print(f"[ingest] shutting down, {event_count} events ingested")


if __name__ == "__main__":
    run()
