"""Determinism and fault-profile tests for the synthetic simulator."""

import hashlib

import pytest

from edge_evidence.simulator import (
    Scenario,
    SimulatorConfig,
    canonical_jsonl,
    generate_records,
)
from edge_evidence.stream import inspect_stream


def test_same_configuration_is_byte_identical() -> None:
    config = SimulatorConfig(seed=2026, count=8)
    first = canonical_jsonl(generate_records(config))
    second = canonical_jsonl(generate_records(config))
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


@pytest.mark.parametrize(
    ("scenario", "expected_code"),
    [
        (Scenario.DELAYED, "delayed_arrival"),
        (Scenario.DUPLICATE, "duplicate_event_id"),
        (Scenario.REORDERED, "source_sequence_regression"),
        (Scenario.MALFORMED, "invalid_event"),
    ],
)
def test_fault_profiles_are_distinguishable(
    scenario: Scenario, expected_code: str
) -> None:
    records = generate_records(SimulatorConfig(count=6, scenario=scenario))
    codes = {finding.code for finding in inspect_stream(records)}
    assert expected_code in codes


def test_baseline_has_no_findings() -> None:
    records = generate_records(SimulatorConfig(count=6))
    assert inspect_stream(records) == ()
