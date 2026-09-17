"""M9A historical import contract with synthetic, non-private records."""

import json
from datetime import UTC, datetime

from edge_evidence.historical import (
    HistoricalImportConfig,
    qualify_historical_jsonl,
)


def _config(key: bytes = b"synthetic-test-key-only") -> HistoricalImportConfig:
    return HistoricalImportConfig(
        pseudonym_key=key,
        imported_at=datetime(2026, 9, 17, tzinfo=UTC),
        archive_sha256="a" * 64,
    )


def _write_jsonl(tmp_path, records):
    path = tmp_path / "historical.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for item in records))
    return path


def _primary(event_id: str, source: str = "PRIVATE-DEVICE") -> dict:
    return {
        "event_id": event_id,
        "quality": {"epistemic_state": "VALID", "reason": None},
        "schema_version": "1.0",
        "sensor": "PRIVATE-SENSOR",
        "signal": {"temperature": 21.5},
        "source": source,
        "ts": "2026-02-13T00:00:00Z",
    }


def test_primary_mapping_is_private_and_replayable(tmp_path) -> None:
    source = _write_jsonl(tmp_path, [_primary("original-event-1")])
    result = qualify_historical_jsonl(source, config=_config())

    assert result.report["event_count"] == 1
    assert result.report["independent_replay_match"] is True
    assert result.report["rejection_count"] == 0
    assert result.events[0].source_sequence == 0
    assert result.events[0].event_type == "private-sensor"
    canonical = result.events[0].canonical_json()
    assert "PRIVATE-DEVICE" not in canonical
    assert "original-event-1" not in canonical
    assert "PRIVATE-SENSOR" not in canonical


def test_control_shape_and_sequences_are_deterministic(tmp_path) -> None:
    records = [
        {
            "event_id": f"control-{index}",
            "signal": {"status": "restored"},
            "source": "PRIVATE-CONTROLLER",
            "ts_utc": f"2026-02-13T00:00:0{index}Z",
            "type": "SYSTEM_RECONNECT",
        }
        for index in range(2)
    ]
    source = _write_jsonl(tmp_path, records)
    first = qualify_historical_jsonl(source, config=_config())
    second = qualify_historical_jsonl(source, config=_config())

    assert [event.source_sequence for event in first.events] == [0, 1]
    assert first.events[0].event_type == "system_reconnect"
    assert first.report == second.report
    assert [event.canonical_json() for event in first.events] == [
        event.canonical_json() for event in second.events
    ]


def test_different_private_key_changes_public_identities(tmp_path) -> None:
    source = _write_jsonl(tmp_path, [_primary("event-1")])
    first = qualify_historical_jsonl(source, config=_config())
    second = qualify_historical_jsonl(
        source, config=_config(b"different-synthetic-key")
    )

    assert first.events[0].event_id != second.events[0].event_id
    assert first.events[0].source_id != second.events[0].source_id


def test_invalid_and_duplicate_records_are_counted_without_content(tmp_path) -> None:
    duplicate = _primary("event-1")
    source = tmp_path / "historical.jsonl"
    source.write_text(
        json.dumps(_primary("event-1"))
        + "\n"
        + json.dumps(duplicate)
        + "\n"
        + "not-json\n"
        + json.dumps({"event_id": "unknown", "source": "private"})
        + "\n"
    )
    result = qualify_historical_jsonl(source, config=_config())

    assert result.report["event_count"] == 1
    assert result.report["rejection_count"] == 3
    assert result.report["rejection_counts"] == {
        "duplicate_event_id": 1,
        "invalid_json": 1,
        "unsupported_record_shape": 1,
    }
    assert "private" not in json.dumps(result.report)
