"""Stateless inspection of canonical event streams."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from edge_evidence.event import CanonicalEvent, EventValidationError


@dataclass(frozen=True, slots=True)
class StreamFinding:
    """A deterministic, machine-readable observation about an input record."""

    code: str
    record_index: int
    event_id: str | None = None


def inspect_stream(
    records: Iterable[Mapping[str, Any]], *, delay_threshold_seconds: int = 60
) -> tuple[StreamFinding, ...]:
    """Classify invalid, duplicate, delayed and reordered input records."""
    seen_ids: set[str] = set()
    last_sequence: dict[str, int] = {}
    findings: list[StreamFinding] = []
    delay_limit = timedelta(seconds=delay_threshold_seconds)

    for index, record in enumerate(records):
        try:
            event = CanonicalEvent.from_mapping(record)
        except EventValidationError:
            findings.append(StreamFinding("invalid_event", index))
            continue

        if event.event_id in seen_ids:
            findings.append(StreamFinding("duplicate_event_id", index, event.event_id))
            continue
        seen_ids.add(event.event_id)

        previous = last_sequence.get(event.source_id)
        if previous is not None and event.source_sequence <= previous:
            findings.append(
                StreamFinding("source_sequence_regression", index, event.event_id)
            )
        last_sequence[event.source_id] = max(
            event.source_sequence, last_sequence.get(event.source_id, -1)
        )

        if event.ingested_at - event.observed_at > delay_limit:
            findings.append(StreamFinding("delayed_arrival", index, event.event_id))

    return tuple(findings)
