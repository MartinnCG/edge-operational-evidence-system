"""Rule traceability, ordering and interpretation boundaries for M4."""

from copy import deepcopy
from datetime import timedelta

import pytest

from edge_evidence.event import CanonicalEvent
from edge_evidence.ledger import EventLedger
from edge_evidence.quality import QualityPolicy, evaluate_quality
from edge_evidence.simulator import Scenario, SimulatorConfig, generate_records


def _evaluate(tmp_path, records, *, name="ledger.db"):
    events = [CanonicalEvent.from_mapping(record) for record in records]
    latest = max(event.observed_at for event in events)
    with EventLedger(tmp_path / name) as ledger:
        ledger.ingest_many(events)
        return evaluate_quality(
            ledger.read_events(), as_of=latest + timedelta(seconds=1)
        )


def test_finding_binds_rule_version_and_supporting_evidence(tmp_path) -> None:
    records = generate_records(
        SimulatorConfig(count=6, scenario=Scenario.DELAYED)
    )
    findings = _evaluate(tmp_path, records)
    delayed = next(item for item in findings if item.code == "delayed_arrival")
    assert delayed.rule_id == "DQ-001"
    assert delayed.rule_version == "1.0"
    assert len(delayed.finding_id) == 64
    assert delayed.event_ids
    assert delayed.ledger_ordinals
    assert delayed.evidence["delay_seconds"] == 120.0


def test_sequence_gap_is_independent_of_append_arrival_order(tmp_path) -> None:
    records = generate_records(SimulatorConfig(count=6))
    records.pop(2)
    ordered = _evaluate(tmp_path, records, name="ordered.db")
    changed_order = [records[3], records[0], records[4], records[1], records[2]]
    reordered = _evaluate(tmp_path, changed_order, name="reordered.db")
    first = next(item for item in ordered if item.code == "source_sequence_gap")
    second = next(item for item in reordered if item.code == "source_sequence_gap")
    assert first.evidence == second.evidence
    assert set(first.event_ids) == set(second.event_ids)


def test_evaluation_does_not_mutate_source_records(tmp_path) -> None:
    records = generate_records(SimulatorConfig(count=5))
    before = deepcopy(records)
    _evaluate(tmp_path, records)
    assert records == before


def test_staleness_requires_explicit_utc_time(tmp_path) -> None:
    records = generate_records(SimulatorConfig(count=4))
    events = [CanonicalEvent.from_mapping(record) for record in records]
    with EventLedger(tmp_path / "ledger.db") as ledger:
        ledger.ingest_many(events)
        with pytest.raises(ValueError, match="as_of must use UTC"):
            evaluate_quality(
                ledger.read_events(), as_of=events[-1].observed_at.replace(tzinfo=None)
            )


def test_repeated_payload_is_not_declared_sensor_failure(tmp_path) -> None:
    records = generate_records(SimulatorConfig(count=5))
    for index in range(1, 4):
        records[index]["payload"] = dict(records[0]["payload"])
    findings = _evaluate(tmp_path, records)
    repeated = next(item for item in findings if item.code == "repeated_payload_run")
    assert "sensor failure is not inferred" in repeated.interpretation


def test_policy_version_and_thresholds_fail_closed() -> None:
    with pytest.raises(ValueError, match="unsupported quality policy"):
        QualityPolicy(version="2.0")
    with pytest.raises(ValueError, match="at least 2"):
        QualityPolicy(frozen_run_length=1)
