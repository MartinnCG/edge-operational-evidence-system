"""Executable examples for canonical event contract version 1.0."""

from copy import deepcopy

import pytest

from edge_evidence.event import CanonicalEvent, EventValidationError
from edge_evidence.simulator import SimulatorConfig, generate_records


@pytest.fixture
def record() -> dict:
    return generate_records(SimulatorConfig(count=2))[0]


def test_round_trip_is_lossless_and_canonical(record: dict) -> None:
    event = CanonicalEvent.from_mapping(record)
    rebuilt = CanonicalEvent.from_mapping(event.to_mapping())
    assert rebuilt == event
    assert rebuilt.canonical_json() == event.canonical_json()


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (lambda item: item.pop("event_id"), "missing_field"),
        (
            lambda item: item.update(schema_version="999.0"),
            "unsupported_schema_version",
        ),
        (lambda item: item.update(source_sequence=-1), "invalid_source_sequence"),
        (lambda item: item.update(extra="not allowed"), "unknown_field"),
    ],
)
def test_invalid_records_fail_closed(record: dict, change, code: str) -> None:
    candidate = deepcopy(record)
    change(candidate)
    with pytest.raises(EventValidationError) as captured:
        CanonicalEvent.from_mapping(candidate)
    assert captured.value.code == code
