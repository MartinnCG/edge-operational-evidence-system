"""Executable durability, immutability and idempotency claims for M2."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import (
    EventIdentityConflict,
    EventLedger,
    IngestStatus,
    SourceSequenceConflict,
)
from edge_evidence.simulator import SimulatorConfig, generate_records


def _events(count: int = 4) -> list[CanonicalEvent]:
    return [
        CanonicalEvent.from_mapping(record)
        for record in generate_records(SimulatorConfig(count=count))
    ]


def test_identical_retry_is_idempotent(tmp_path) -> None:
    event = _events(2)[0]
    with EventLedger(tmp_path / "ledger.db") as ledger:
        first = ledger.ingest(event)
        second = ledger.ingest(event)
        assert first.status is IngestStatus.ACCEPTED
        assert second.status is IngestStatus.DUPLICATE
        assert second.ordinal == first.ordinal
        assert second.content_sha256 == first.content_sha256
        assert ledger.count() == 1


def test_event_identity_conflict_fails_closed(tmp_path) -> None:
    original = _events(2)[0]
    changed = original.to_mapping()
    changed["payload"] = {"temperature_c": 99.0}
    with EventLedger(tmp_path / "ledger.db") as ledger:
        ledger.ingest(original)
        with pytest.raises(EventIdentityConflict):
            ledger.ingest(changed)
        assert ledger.count() == 1


def test_source_sequence_collision_fails_closed(tmp_path) -> None:
    original = _events(2)[0]
    collision = original.to_mapping()
    collision["event_id"] = "synthetic-collision"
    with EventLedger(tmp_path / "ledger.db") as ledger:
        ledger.ingest(original)
        with pytest.raises(SourceSequenceConflict):
            ledger.ingest(collision)
        assert ledger.count() == 1


def test_batch_conflict_rolls_back_all_rows(tmp_path) -> None:
    records = [event.to_mapping() for event in _events(3)]
    conflict = deepcopy(records[0])
    conflict["payload"] = {"temperature_c": 99.0}
    records.append(conflict)
    with EventLedger(tmp_path / "ledger.db") as ledger:
        with pytest.raises(EventIdentityConflict):
            ledger.ingest_many(records)
        assert ledger.count() == 0


def test_committed_batch_is_returned_in_append_order(tmp_path) -> None:
    events = _events(4)
    with EventLedger(tmp_path / "ledger.db") as ledger:
        results = ledger.ingest_many(events)
        stored = ledger.read_events()
    assert [result.ordinal for result in results] == [1, 2, 3, 4]
    assert [item.event.event_id for item in stored] == [
        event.event_id for event in events
    ]


def test_database_reopen_preserves_content_and_digest(tmp_path) -> None:
    path = tmp_path / "ledger.db"
    event = _events(2)[0]
    with EventLedger(path) as ledger:
        accepted = ledger.ingest(event)
    with EventLedger(path) as reopened:
        stored = reopened.read_events()
    assert len(stored) == 1
    assert stored[0].event == event
    assert stored[0].content_sha256 == accepted.content_sha256


@pytest.mark.parametrize(
    "statement", ["UPDATE events SET event_type = 'x'", "DELETE FROM events"]
)
def test_database_triggers_reject_mutation(tmp_path, statement: str) -> None:
    path = tmp_path / "ledger.db"
    with EventLedger(path) as ledger:
        ledger.ingest(_events(2)[0])
    connection = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            connection.execute(statement)
    finally:
        connection.close()


def test_concurrent_retries_create_one_row(tmp_path) -> None:
    path = tmp_path / "ledger.db"
    event = _events(2)[0]
    with EventLedger(path):
        pass

    def retry() -> IngestStatus:
        with EventLedger(path) as ledger:
            return ledger.ingest(event).status

    with ThreadPoolExecutor(max_workers=4) as executor:
        statuses = list(executor.map(lambda _: retry(), range(8)))
    assert statuses.count(IngestStatus.ACCEPTED) == 1
    assert statuses.count(IngestStatus.DUPLICATE) == 7
    with EventLedger(path) as ledger:
        assert ledger.count() == 1
