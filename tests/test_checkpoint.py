"""Checkpoint round-trip and corruption tests."""

import json

import pytest

from edge_evidence.checkpoint import CheckpointError, load_checkpoint, write_checkpoint
from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.projection import replay
from edge_evidence.simulator import SimulatorConfig, generate_records


def _projection(tmp_path):
    records = generate_records(SimulatorConfig(count=4))
    events = [CanonicalEvent.from_mapping(record) for record in records]
    with EventLedger(tmp_path / "ledger.db") as ledger:
        ledger.ingest_many(events)
        return replay(ledger)


def test_checkpoint_round_trip_preserves_projection(tmp_path) -> None:
    projection = _projection(tmp_path)
    path = tmp_path / "state" / "checkpoint.json"
    write_checkpoint(path, projection)
    assert load_checkpoint(path) == projection


def test_checkpoint_state_corruption_fails_closed(tmp_path) -> None:
    projection = _projection(tmp_path)
    path = tmp_path / "checkpoint.json"
    write_checkpoint(path, projection)
    document = json.loads(path.read_text())
    document["state"]["event_count"] += 1
    path.write_text(json.dumps(document))
    with pytest.raises(CheckpointError) as captured:
        load_checkpoint(path)
    assert captured.value.code == "state_digest_mismatch"


def test_unsupported_checkpoint_projector_fails_closed(tmp_path) -> None:
    projection = _projection(tmp_path)
    path = tmp_path / "checkpoint.json"
    write_checkpoint(path, projection)
    document = json.loads(path.read_text())
    document["projector_version"] = "2.0"
    path.write_text(json.dumps(document))
    with pytest.raises(CheckpointError) as captured:
        load_checkpoint(path)
    assert captured.value.code == "unsupported_projector_version"


def test_invalid_json_checkpoint_fails_closed(tmp_path) -> None:
    path = tmp_path / "checkpoint.json"
    path.write_text("not-json")
    with pytest.raises(CheckpointError) as captured:
        load_checkpoint(path)
    assert captured.value.code == "unreadable_checkpoint"
