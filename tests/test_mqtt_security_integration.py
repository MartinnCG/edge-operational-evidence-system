"""Opt-in mutual-TLS and ACL campaign against real Mosquitto."""

# ruff: noqa: E402

import os
import ssl
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

if os.environ.get("MQTT_SECURITY_INTEGRATION") != "1":
    pytest.skip(
        "set MQTT_SECURITY_INTEGRATION=1 with secure Mosquitto running",
        allow_module_level=True,
    )

import paho.mqtt.client as mqtt

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.mqtt import MqttIngestionRuntime, event_to_mqtt
from edge_evidence.paho_consumer import (
    PahoConsumerConfig,
    PahoMqttConsumer,
    PahoTlsConfig,
)
from edge_evidence.simulator import SimulatorConfig, generate_records

HOST = "localhost"
PORT = 18884
PKI = Path("ops/mqtt-secure/generated")
RECEIVED_AT = datetime(2026, 1, 1, 1, tzinfo=UTC)


def _wait(predicate, *, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("timed out waiting for secure broker condition")


def _client(cert_name: str | None) -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"m8-{cert_name or 'anonymous'}-{uuid.uuid4()}",
        protocol=mqtt.MQTTv311,
    )
    tls = {"ca_certs": str(PKI / "ca.crt"), "tls_version": ssl.PROTOCOL_TLS_CLIENT}
    if cert_name is not None:
        tls.update(
            {
                "certfile": str(PKI / f"{cert_name}.crt"),
                "keyfile": str(PKI / f"{cert_name}.key"),
            }
        )
    client.tls_set(**tls)
    client.tls_insecure_set(False)
    return client


def _publish(event: CanonicalEvent, *, cert_name: str) -> None:
    topic, payload = event_to_mqtt(event)
    client = _client(cert_name)
    client.connect(HOST, PORT, keepalive=10)
    client.loop_start()
    info = client.publish(topic, payload, qos=1)
    info.wait_for_publish(timeout=5)
    client.disconnect()
    client.loop_stop()


def _attempt_forbidden_publish(event: CanonicalEvent, *, cert_name: str) -> None:
    topic, payload = event_to_mqtt(event)
    client = _client(cert_name)
    client.connect(HOST, PORT, keepalive=10)
    client.loop_start()
    client.publish(topic, payload, qos=1)
    time.sleep(0.5)
    client.disconnect()
    client.loop_stop()


def _assert_tls_rejected(cert_name: str | None) -> None:
    client = _client(cert_name)
    with pytest.raises((ssl.SSLError, ConnectionError, OSError)):
        client.connect(HOST, PORT, keepalive=10)


@pytest.mark.integration
def test_mtls_identity_and_role_acl_fail_closed(tmp_path: Path) -> None:
    events = [
        CanonicalEvent.from_mapping(record)
        for record in generate_records(SimulatorConfig(seed=2028, count=2))
    ]
    tls = PahoTlsConfig(
        PKI / "ca.crt",
        PKI / "edge-consumer.crt",
        PKI / "edge-consumer.key",
    )
    with EventLedger(tmp_path / "secure-ledger.sqlite3") as ledger:
        runtime = MqttIngestionRuntime(ledger)
        consumer = PahoMqttConsumer(
            runtime,
            PahoConsumerConfig(
                host=HOST,
                port=PORT,
                client_id="m8-secure-consumer",
                tls=tls,
            ),
            clock=lambda: RECEIVED_AT,
        )
        consumer.start()
        try:
            _assert_tls_rejected(None)
            _assert_tls_rejected("rogue-client")

            _publish(events[0], cert_name="edge-publisher")
            _wait(lambda: ledger.count() == 1)

            _attempt_forbidden_publish(events[1], cert_name="edge-consumer")
            time.sleep(0.5)
            assert ledger.count() == 1

            _publish(events[1], cert_name="edge-publisher")
            _wait(lambda: ledger.count() == 2)
            assert runtime.metrics.accepted == 2
            assert runtime.metrics.rejected == 0
            assert consumer.callback_errors == ()
        finally:
            consumer.stop()
