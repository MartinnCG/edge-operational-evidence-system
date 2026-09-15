"""Strict MQTT boundary and observable ingestion tests."""

import json
from datetime import UTC, datetime, timedelta

import pytest

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.mqtt import (
    DeliveryDisposition,
    MqttAdapterError,
    MqttIngestionRuntime,
    event_to_mqtt,
    mqtt_to_event,
)
from edge_evidence.simulator import SimulatorConfig, generate_records


def _event() -> CanonicalEvent:
    return CanonicalEvent.from_mapping(generate_records(SimulatorConfig(count=2))[0])


def test_round_trip_preserves_canonical_event() -> None:
    event = _event()
    topic, payload = event_to_mqtt(event)
    decoded = mqtt_to_event(topic, payload, received_at=event.ingested_at)
    assert decoded.canonical_json() == event.canonical_json()


@pytest.mark.parametrize(
    ("topic", "code"),
    [
        ("other/v1/source/type", "unsupported_topic"),
        ("edge-evidence/v2/source/type", "unsupported_topic"),
        ("edge-evidence/v1/source", "unsupported_topic"),
        ("edge-evidence/v1/source/type/extra", "unsupported_topic"),
    ],
)
def test_topic_contract_fails_closed(topic: str, code: str) -> None:
    _, payload = event_to_mqtt(_event())
    with pytest.raises(MqttAdapterError, match="expected") as captured:
        mqtt_to_event(topic, payload, received_at=_event().ingested_at)
    assert captured.value.code == code


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (b"\xff", "payload_not_utf8"),
        (b"not-json", "payload_not_json"),
        (b"[]", "payload_not_object"),
        (b"{}", "missing_payload_field"),
    ],
)
def test_payload_contract_fails_closed(payload: bytes, code: str) -> None:
    topic, _ = event_to_mqtt(_event())
    with pytest.raises(MqttAdapterError) as captured:
        mqtt_to_event(topic, payload, received_at=_event().ingested_at)
    assert captured.value.code == code


def test_unknown_payload_authority_is_rejected() -> None:
    event = _event()
    topic, payload = event_to_mqtt(event)
    document = json.loads(payload)
    document["source_id"] = "attempted.second-authority"
    with pytest.raises(MqttAdapterError) as captured:
        mqtt_to_event(
            topic,
            json.dumps(document).encode(),
            received_at=event.ingested_at,
        )
    assert captured.value.code == "unknown_payload_field"


def test_received_at_must_be_explicit_utc() -> None:
    topic, payload = event_to_mqtt(_event())
    with pytest.raises(MqttAdapterError) as captured:
        mqtt_to_event(topic, payload, received_at=datetime(2026, 1, 1))
    assert captured.value.code == "received_at_not_utc"


def test_redelivery_is_observable_and_idempotent() -> None:
    event = _event()
    topic, payload = event_to_mqtt(event)
    with EventLedger(":memory:") as ledger:
        runtime = MqttIngestionRuntime(ledger)
        first = runtime.ingest(topic, payload, received_at=event.ingested_at)
        second = runtime.ingest(
            topic, payload, received_at=event.ingested_at + timedelta(minutes=5)
        )
        assert first.disposition is DeliveryDisposition.ACCEPTED
        assert second.disposition is DeliveryDisposition.DUPLICATE
        assert first.ledger_ordinal == second.ledger_ordinal == 1
        assert ledger.count() == 1
        assert ledger.read_events()[0].event.ingested_at == event.ingested_at
        assert runtime.metrics.to_mapping() == {
            "accepted": 1,
            "disconnects": 0,
            "duplicates": 1,
            "messages_received": 2,
            "reconnects": 0,
            "rejected": 0,
        }


def test_invalid_message_does_not_reach_ledger() -> None:
    with EventLedger(":memory:") as ledger:
        runtime = MqttIngestionRuntime(ledger)
        result = runtime.ingest(
            "bad/topic", b"{}", received_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
        assert result.disposition is DeliveryDisposition.REJECTED
        assert result.rejection_code == "unsupported_topic"
        assert ledger.count() == 0
        assert runtime.metrics.rejected == 1


def test_identity_conflict_is_rejected_without_mutation() -> None:
    event = _event()
    topic, payload = event_to_mqtt(event)
    altered = json.loads(payload)
    altered["payload"]["temperature_c"] = -999
    with EventLedger(":memory:") as ledger:
        runtime = MqttIngestionRuntime(ledger)
        runtime.ingest(topic, payload, received_at=event.ingested_at)
        result = runtime.ingest(
            topic,
            json.dumps(altered).encode(),
            received_at=event.ingested_at,
        )
        assert result.rejection_code == "ledger_identity_conflict"
        assert ledger.count() == 1
