"""Opt-in integration campaign against a real local Mosquitto broker."""

# ruff: noqa: E402

import os
import subprocess
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

if os.environ.get("MQTT_INTEGRATION") != "1":
    pytest.skip(
        "set MQTT_INTEGRATION=1 with Mosquitto running", allow_module_level=True
    )

import paho.mqtt.client as mqtt

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.mqtt import MqttIngestionRuntime, event_to_mqtt
from edge_evidence.paho_consumer import PahoConsumerConfig, PahoMqttConsumer
from edge_evidence.simulator import SimulatorConfig, generate_records

HOST = "127.0.0.1"
PORT = 18883
COMPOSE_FILE = Path("ops/mqtt/compose.yml")
RECEIVED_AT = datetime(2026, 1, 1, 1, tzinfo=UTC)


def _wait(predicate, *, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for broker condition")


def _publish(event: CanonicalEvent, *, retain: bool = False) -> None:
    topic, payload = event_to_mqtt(event)
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"m7-publisher-{uuid.uuid4()}",
        protocol=mqtt.MQTTv311,
    )
    client.connect(HOST, PORT, keepalive=10)
    client.loop_start()
    info = client.publish(topic, payload, qos=1, retain=retain)
    info.wait_for_publish(timeout=10)
    client.disconnect()
    client.loop_stop()
    assert info.is_published()


def _compose(action: str) -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), action, "mosquitto"],
        check=True,
    )


@pytest.mark.integration
def test_real_broker_retained_qos_redelivery_and_reconnect(tmp_path: Path) -> None:
    events = [
        CanonicalEvent.from_mapping(record)
        for record in generate_records(SimulatorConfig(seed=2027, count=3))
    ]
    _publish(events[0], retain=True)
    with EventLedger(tmp_path / "broker-ledger.sqlite3") as ledger:
        runtime = MqttIngestionRuntime(ledger)
        consumer = PahoMqttConsumer(
            runtime,
            PahoConsumerConfig(port=PORT, client_id="m7-integration-consumer"),
            clock=lambda: RECEIVED_AT,
        )
        consumer.start()
        try:
            _wait(lambda: ledger.count() == 1)
            _publish(events[0])
            _publish(events[1])
            _wait(lambda: ledger.count() == 2 and runtime.metrics.duplicates == 1)

            _compose("stop")
            _wait(lambda: runtime.metrics.disconnects >= 1)
            _compose("start")
            _wait(
                lambda: consumer.wait_until_connected(0.05)
                and runtime.metrics.reconnects >= 1,
                timeout=20,
            )
            consumer._clock = lambda: RECEIVED_AT + timedelta(minutes=1)
            _publish(events[2])
            _wait(lambda: ledger.count() == 3)

            assert runtime.metrics.accepted == 3
            assert runtime.metrics.duplicates == 1
            assert runtime.metrics.rejected == 0
            assert consumer.callback_errors == ()
        finally:
            consumer.stop()
