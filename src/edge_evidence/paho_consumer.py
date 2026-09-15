"""Concrete Paho MQTT consumer for the broker-neutral M6 runtime."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from edge_evidence.mqtt import MQTT_TOPIC_ROOT, DeliveryResult, MqttIngestionRuntime

PAHO_CONSUMER_VERSION = "1.0"


class PahoUnavailableError(RuntimeError):
    """The optional Paho integration dependency is not installed."""


class BrokerConnectionError(RuntimeError):
    """The broker did not accept or establish the requested connection."""


@dataclass(frozen=True, slots=True)
class PahoConsumerConfig:
    host: str = "127.0.0.1"
    port: int = 1883
    client_id: str = "edge-evidence-consumer-v1"
    topic_filter: str = f"{MQTT_TOPIC_ROOT}/+/+"
    qos: int = 1
    keepalive_seconds: int = 10

    def __post_init__(self) -> None:
        if not self.host:
            raise ValueError("host must not be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.client_id:
            raise ValueError("client_id must not be empty")
        if self.qos != 1:
            raise ValueError("M7 consumer requires QoS 1")
        if self.keepalive_seconds <= 0:
            raise ValueError("keepalive_seconds must be positive")


def _load_paho() -> ModuleType:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as error:
        raise PahoUnavailableError(
            "install the mqtt extra: python -m pip install '.[mqtt]'"
        ) from error
    return mqtt


class PahoMqttConsumer:
    """Own a Paho network loop and acknowledge after runtime classification."""

    def __init__(
        self,
        runtime: MqttIngestionRuntime,
        config: PahoConsumerConfig | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        mqtt_module: ModuleType | Any | None = None,
    ) -> None:
        self.runtime = runtime
        self.config = config or PahoConsumerConfig()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mqtt = mqtt_module or _load_paho()
        self._connected = threading.Event()
        self._ever_connected = False
        self._connection_failures = 0
        self._callback_errors: list[str] = []
        self._last_delivery: DeliveryResult | None = None
        self._lock = threading.RLock()
        self._client = self._mqtt.Client(
            callback_api_version=self._mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.config.client_id,
            clean_session=False,
            protocol=self._mqtt.MQTTv311,
            reconnect_on_failure=True,
            manual_ack=True,
        )
        self._client.reconnect_delay_set(min_delay=1, max_delay=2)
        self._client.on_connect = self._on_connect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    @property
    def callback_errors(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._callback_errors)

    @property
    def last_delivery(self) -> DeliveryResult | None:
        with self._lock:
            return self._last_delivery

    @property
    def connection_failures(self) -> int:
        with self._lock:
            return self._connection_failures

    def _record_connection_failure(self) -> None:
        with self._lock:
            self._connection_failures += 1

    def _record_error(self, code: str) -> None:
        with self._lock:
            self._callback_errors.append(code)

    def _on_connect(
        self, client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any
    ) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            self._record_connection_failure()
            return
        result, _message_id = client.subscribe(
            self.config.topic_filter, qos=self.config.qos
        )
        if result != self._mqtt.MQTT_ERR_SUCCESS:
            self._record_error(f"subscribe_failed:{result}")
            return
        if self._ever_connected:
            self.runtime.record_reconnect()
        self._ever_connected = True
        self._connected.set()

    def _on_connect_fail(self, client: Any, userdata: Any) -> None:
        del client, userdata
        self._record_connection_failure()

    def _on_disconnect(
        self,
        client: Any,
        userdata: Any,
        disconnect_flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        del client, userdata, disconnect_flags, properties
        self._connected.clear()
        if reason_code != 0:
            self.runtime.record_disconnect()

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        del userdata
        try:
            delivery = self.runtime.ingest(
                message.topic,
                bytes(message.payload),
                received_at=self._clock(),
            )
            if message.qos > 0:
                result = client.ack(message.mid, message.qos)
                if result != self._mqtt.MQTT_ERR_SUCCESS:
                    self._record_error(f"ack_failed:{result}")
                    return
            with self._lock:
                self._last_delivery = delivery
        except Exception as error:  # keep failed processing unacknowledged
            self._record_error(f"message_processing_failed:{type(error).__name__}")

    def start(self, *, timeout_seconds: float = 10.0) -> None:
        self._client.connect_async(
            self.config.host,
            self.config.port,
            keepalive=self.config.keepalive_seconds,
        )
        self._client.loop_start()
        if not self._connected.wait(timeout_seconds):
            self._client.loop_stop()
            errors = ",".join(self.callback_errors)
            if not errors:
                errors = f"timeout; connection_failures={self.connection_failures}"
            raise BrokerConnectionError(f"broker connection failed: {errors}")

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def wait_until_connected(self, timeout_seconds: float = 10.0) -> bool:
        return self._connected.wait(timeout_seconds)
