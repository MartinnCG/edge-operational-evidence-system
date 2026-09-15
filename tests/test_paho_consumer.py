"""Broker-free unit tests for the concrete Paho callback adapter."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.mqtt import DeliveryDisposition, MqttIngestionRuntime, event_to_mqtt
from edge_evidence.paho_consumer import (
    BrokerConnectionError,
    PahoConsumerConfig,
    PahoMqttConsumer,
)
from edge_evidence.simulator import SimulatorConfig, generate_records


class _FakeCallbackVersion:
    VERSION2 = 2


class _FakeClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.on_connect = None
        self.on_connect_fail = None
        self.on_disconnect = None
        self.on_message = None
        self.acks: list[tuple[int, int]] = []
        self.subscriptions: list[tuple[str, int]] = []
        self.connect_args = None
        self.loop_started = False
        self.assert_before_ack = None

    def reconnect_delay_set(self, *, min_delay: int, max_delay: int) -> None:
        self.delays = (min_delay, max_delay)

    def subscribe(self, topic: str, *, qos: int):
        self.subscriptions.append((topic, qos))
        return 0, 1

    def ack(self, message_id: int, qos: int) -> int:
        if self.assert_before_ack is not None:
            self.assert_before_ack()
        self.acks.append((message_id, qos))
        return 0

    def connect_async(self, host: str, port: int, *, keepalive: int) -> None:
        self.connect_args = (host, port, keepalive)

    def loop_start(self) -> None:
        self.loop_started = True
        if self.on_connect is not None:
            self.on_connect(self, None, None, 0, None)

    def disconnect(self) -> None:
        if self.on_disconnect is not None:
            self.on_disconnect(self, None, None, 0, None)

    def loop_stop(self) -> None:
        self.loop_started = False


class _FakeMqtt:
    CallbackAPIVersion = _FakeCallbackVersion
    MQTTv311 = 4
    MQTT_ERR_SUCCESS = 0

    def __init__(self) -> None:
        self.client = None

    def Client(self, **kwargs):
        self.client = _FakeClient(**kwargs)
        return self.client


def _event() -> CanonicalEvent:
    return CanonicalEvent.from_mapping(generate_records(SimulatorConfig(count=2))[0])


def _consumer(ledger: EventLedger, module: _FakeMqtt) -> PahoMqttConsumer:
    return PahoMqttConsumer(
        MqttIngestionRuntime(ledger),
        clock=lambda: datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
        mqtt_module=module,
    )


def test_configuration_requires_qos_one() -> None:
    with pytest.raises(ValueError, match="QoS 1"):
        PahoConsumerConfig(qos=0)


def test_client_uses_callback_v2_manual_ack_and_persistent_session() -> None:
    module = _FakeMqtt()
    with EventLedger(":memory:") as ledger:
        consumer = _consumer(ledger, module)
        assert module.client.kwargs == {
            "callback_api_version": 2,
            "clean_session": False,
            "client_id": "edge-evidence-consumer-v1",
            "manual_ack": True,
            "protocol": 4,
            "reconnect_on_failure": True,
        }
        consumer.start()
        assert module.client.subscriptions == [("edge-evidence/v1/+/+", 1)]
        consumer.stop()


def test_qos_message_is_acknowledged_only_after_commit() -> None:
    module = _FakeMqtt()
    event = _event()
    topic, payload = event_to_mqtt(event)
    with EventLedger(":memory:") as ledger:
        consumer = _consumer(ledger, module)
        def assert_committed() -> None:
            assert ledger.count() == 1

        module.client.assert_before_ack = assert_committed
        message = SimpleNamespace(topic=topic, payload=payload, qos=1, mid=42)
        consumer._on_message(module.client, None, message)
        assert ledger.count() == 1
        assert module.client.acks == [(42, 1)]
        assert consumer.last_delivery.disposition is DeliveryDisposition.ACCEPTED


def test_failed_processing_is_not_acknowledged() -> None:
    module = _FakeMqtt()
    with EventLedger(":memory:") as ledger:
        runtime = MqttIngestionRuntime(ledger)
        runtime.ingest = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError())
        consumer = PahoMqttConsumer(runtime, mqtt_module=module)
        message = SimpleNamespace(topic="any", payload=b"{}", qos=1, mid=7)
        consumer._on_message(module.client, None, message)
        assert module.client.acks == []
        assert consumer.callback_errors == ("message_processing_failed:RuntimeError",)


def test_unexpected_disconnect_and_reconnect_are_observable() -> None:
    module = _FakeMqtt()
    with EventLedger(":memory:") as ledger:
        consumer = _consumer(ledger, module)
        consumer._on_connect(module.client, None, None, 0, None)
        consumer._on_disconnect(module.client, None, None, 7, None)
        consumer._on_connect(module.client, None, None, 0, None)
        assert consumer.runtime.metrics.disconnects == 1
        assert consumer.runtime.metrics.reconnects == 1


def test_connection_timeout_fails_explicitly() -> None:
    module = _FakeMqtt()
    with EventLedger(":memory:") as ledger:
        consumer = _consumer(ledger, module)
        module.client.on_connect = None
        with pytest.raises(BrokerConnectionError, match="timeout"):
            consumer.start(timeout_seconds=0.001)


def test_connect_failures_are_observable_without_processing_error() -> None:
    module = _FakeMqtt()
    with EventLedger(":memory:") as ledger:
        consumer = _consumer(ledger, module)
        consumer._on_connect_fail(module.client, None)
        consumer._on_connect(module.client, None, None, 5, None)
        assert consumer.connection_failures == 2
        assert consumer.callback_errors == ()
