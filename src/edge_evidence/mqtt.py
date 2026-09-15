"""Strict MQTT message boundary with observable ledger ingestion."""

from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from edge_evidence.event import CanonicalEvent, EventValidationError
from edge_evidence.ledger import EventLedger, IngestStatus, LedgerConflictError

MQTT_ADAPTER_VERSION = "1.0"
MQTT_TOPIC_ROOT = "edge-evidence/v1"
_PAYLOAD_FIELDS = {
    "event_id",
    "metadata",
    "observed_at",
    "payload",
    "source_sequence",
}


class MqttAdapterError(ValueError):
    """A rejected MQTT delivery with a stable machine-readable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _received_at(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise MqttAdapterError("received_at_not_utc", "received_at must use UTC")
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def event_to_mqtt(event: CanonicalEvent) -> tuple[str, bytes]:
    """Encode a canonical event into the supported topic/payload boundary."""
    mapped = event.to_mapping()
    topic = f"{MQTT_TOPIC_ROOT}/{event.source_id}/{event.event_type}"
    payload = {
        "event_id": mapped["event_id"],
        "metadata": mapped["metadata"],
        "observed_at": mapped["observed_at"],
        "payload": mapped["payload"],
        "source_sequence": mapped["source_sequence"],
    }
    return topic, json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def mqtt_to_event(
    topic: str, payload: bytes, *, received_at: datetime
) -> CanonicalEvent:
    """Map one MQTT delivery into the canonical event contract."""
    if not isinstance(topic, str):
        raise MqttAdapterError("invalid_topic_type", "topic must be text")
    parts = topic.split("/")
    if len(parts) != 4 or parts[:2] != ["edge-evidence", "v1"]:
        raise MqttAdapterError(
            "unsupported_topic", f"expected {MQTT_TOPIC_ROOT}/<source>/<event-type>"
        )
    source_id, event_type = parts[2:]
    if not isinstance(payload, bytes):
        raise MqttAdapterError("invalid_payload_type", "payload must be bytes")
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise MqttAdapterError("payload_not_utf8", "payload must be UTF-8") from error
    try:
        document = json.loads(decoded)
    except json.JSONDecodeError as error:
        raise MqttAdapterError("payload_not_json", "payload must be JSON") from error
    if not isinstance(document, Mapping):
        raise MqttAdapterError("payload_not_object", "payload must be an object")
    missing = _PAYLOAD_FIELDS - document.keys()
    if missing:
        field = sorted(missing)[0]
        raise MqttAdapterError("missing_payload_field", f"missing field: {field}")
    unknown = document.keys() - _PAYLOAD_FIELDS
    if unknown:
        field = sorted(unknown)[0]
        raise MqttAdapterError("unknown_payload_field", f"unknown field: {field}")
    return CanonicalEvent.from_mapping(
        {
            "event_id": document["event_id"],
            "event_type": event_type,
            "ingested_at": _received_at(received_at),
            "metadata": document["metadata"],
            "observed_at": document["observed_at"],
            "payload": document["payload"],
            "schema_version": "1.0",
            "source_id": source_id,
            "source_sequence": document["source_sequence"],
        }
    )


class DeliveryDisposition(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    disposition: DeliveryDisposition
    event_id: str | None = None
    ledger_ordinal: int | None = None
    rejection_code: str | None = None


@dataclass(slots=True)
class RuntimeMetrics:
    messages_received: int = 0
    accepted: int = 0
    duplicates: int = 0
    rejected: int = 0
    disconnects: int = 0
    reconnects: int = 0

    def to_mapping(self) -> dict[str, int]:
        return {
            "accepted": self.accepted,
            "disconnects": self.disconnects,
            "duplicates": self.duplicates,
            "messages_received": self.messages_received,
            "reconnects": self.reconnects,
            "rejected": self.rejected,
        }


class MqttIngestionRuntime:
    """Broker-client-neutral callback target for MQTT message deliveries."""

    def __init__(self, ledger: EventLedger) -> None:
        self.ledger = ledger
        self.metrics = RuntimeMetrics()
        self._lock = threading.RLock()

    def record_disconnect(self) -> None:
        with self._lock:
            self.metrics.disconnects += 1

    def record_reconnect(self) -> None:
        with self._lock:
            self.metrics.reconnects += 1

    def ingest(
        self, topic: str, payload: bytes, *, received_at: datetime
    ) -> DeliveryResult:
        with self._lock:
            return self._ingest_locked(topic, payload, received_at=received_at)

    def _ingest_locked(
        self, topic: str, payload: bytes, *, received_at: datetime
    ) -> DeliveryResult:
        self.metrics.messages_received += 1
        try:
            event = mqtt_to_event(topic, payload, received_at=received_at)
            existing = self.ledger.find_event(event.event_id)
            if existing is not None:
                candidate = event.to_mapping()
                committed = existing.event.to_mapping()
                candidate.pop("ingested_at")
                committed.pop("ingested_at")
                if candidate == committed:
                    event = existing.event
            result = self.ledger.ingest(event)
        except MqttAdapterError as error:
            self.metrics.rejected += 1
            return DeliveryResult(
                DeliveryDisposition.REJECTED, rejection_code=error.code
            )
        except EventValidationError as error:
            self.metrics.rejected += 1
            return DeliveryResult(
                DeliveryDisposition.REJECTED,
                rejection_code=f"event_contract:{error.code}:{error.field}",
            )
        except LedgerConflictError:
            self.metrics.rejected += 1
            return DeliveryResult(
                DeliveryDisposition.REJECTED,
                rejection_code="ledger_identity_conflict",
            )
        if result.status is IngestStatus.ACCEPTED:
            self.metrics.accepted += 1
            disposition = DeliveryDisposition.ACCEPTED
        else:
            self.metrics.duplicates += 1
            disposition = DeliveryDisposition.DUPLICATE
        return DeliveryResult(disposition, result.event_id, result.ordinal)
