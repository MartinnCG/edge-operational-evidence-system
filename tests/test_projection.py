"""Executable determinism and restart-recovery claims for M3."""

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.projection import ProjectionError, project_events, replay
from edge_evidence.simulator import SimulatorConfig, generate_records


def _events(count: int = 6) -> list[CanonicalEvent]:
    return [
        CanonicalEvent.from_mapping(record)
        for record in generate_records(SimulatorConfig(count=count))
    ]


def test_repeated_replay_is_byte_identical(tmp_path) -> None:
    with EventLedger(tmp_path / "ledger.db") as ledger:
        ledger.ingest_many(_events())
        first = replay(ledger)
        second = replay(ledger)
    assert first.canonical_json == second.canonical_json
    assert first.state_sha256 == second.state_sha256


def test_database_reopen_does_not_change_projection(tmp_path) -> None:
    path = tmp_path / "ledger.db"
    with EventLedger(path) as ledger:
        ledger.ingest_many(_events())
        before = replay(ledger)
    with EventLedger(path) as reopened:
        after = replay(reopened)
    assert after == before


def test_equivalent_arrival_orders_produce_same_state_digest(tmp_path) -> None:
    events = _events()
    with EventLedger(tmp_path / "ordered.db") as ordered:
        ordered.ingest_many(events)
        ordered_state = replay(ordered)
    with EventLedger(tmp_path / "reordered.db") as reordered:
        arrival_order = [
            events[3],
            events[0],
            events[5],
            events[1],
            events[4],
            events[2],
        ]
        reordered.ingest_many(arrival_order)
        reordered_state = replay(reordered)
    assert reordered_state.state_sha256 == ordered_state.state_sha256
    assert reordered_state.canonical_json == ordered_state.canonical_json


def test_projection_does_not_mutate_events(tmp_path) -> None:
    events = _events()
    original_mappings = [event.to_mapping() for event in events]
    with EventLedger(tmp_path / "ledger.db") as ledger:
        ledger.ingest_many(events)
        replay(ledger)
    assert [event.to_mapping() for event in events] == original_mappings


def test_empty_ledger_has_stable_state(tmp_path) -> None:
    with EventLedger(tmp_path / "ledger.db") as ledger:
        result = replay(ledger)
    assert result.state["event_count"] == 0
    assert result.state["last_ordinal"] == 0
    assert result.state["sources"] == {}


def test_unsupported_projector_version_fails_closed() -> None:
    try:
        project_events((), projector_version="2.0")
    except ProjectionError as error:
        assert "unsupported projector version" in str(error)
    else:
        raise AssertionError("unsupported projector version was accepted")
