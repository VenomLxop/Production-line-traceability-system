"""Shared helpers for the three station simulator processes."""
import json
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from traceability.config import MQTT_HOST, MQTT_PORT, OPERATOR_POOL


def make_client(client_id: str) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        client_id=client_id,
        clean_session=True,
    )
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    return client


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def random_operator() -> str:
    return random.choice(OPERATOR_POOL)


def random_cycle_time(base: float, jitter: float) -> float:
    return round(max(0.1, random.gauss(base, jitter)), 2)


def random_temperature() -> float:
    # Nominal line temperature with small process noise.
    return round(random.gauss(22.0, 1.5), 2)


def random_pass_fail(fail_rate: float = 0.03) -> str:
    return "fail" if random.random() < fail_rate else "pass"


def build_event(unit_id: str, batch_id: str, station: str) -> dict:
    return {
        "unit_id": unit_id,
        "batch_id": batch_id,
        "station": station,
        "timestamp": now_iso(),
        "operator": random_operator(),
        "cycle_time": random_cycle_time(base=12.0, jitter=2.5),
        "temperature": random_temperature(),
        "pass_fail": random_pass_fail(),
    }


def publish_event(client: mqtt.Client, topic: str, event: dict) -> None:
    client.publish(topic, json.dumps(event), qos=1)


def sleep_between_units(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))
