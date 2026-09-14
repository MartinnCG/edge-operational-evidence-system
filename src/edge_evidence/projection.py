"""Versioned deterministic projection and canonical state digest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from edge_evidence.ledger import EventLedger, StoredEvent

PROJECTOR_VERSION = "1.0"


class ProjectionError(RuntimeError):
    """The input cannot be projected under the requested contract."""


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Canonical state reconstructed from a ledger prefix."""

    state: Mapping[str, Any]
    canonical_json: str
    state_sha256: str


def canonical_state_json(state: Mapping[str, Any]) -> str:
    """Return the only supported byte representation for projected state."""
    return json.dumps(
        state,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def project_events(
    stored_events: Iterable[StoredEvent], *, projector_version: str = PROJECTOR_VERSION
) -> ProjectionResult:
    """Project immutable ledger rows into deterministic per-source state."""
    if projector_version != PROJECTOR_VERSION:
        raise ProjectionError(f"unsupported projector version: {projector_version}")

    sources: dict[str, dict[str, Any]] = {}
    event_count = 0
    last_ordinal = 0
    for stored in stored_events:
        if stored.ordinal <= last_ordinal:
            raise ProjectionError("ledger ordinals must be strictly increasing")
        last_ordinal = stored.ordinal
        event_count += 1
        event = stored.event
        source = sources.setdefault(
            event.source_id,
            {
                "event_count": 0,
                "latest_event_id": None,
                "latest_event_type": None,
                "latest_ingested_at": None,
                "latest_observed_at": None,
                "latest_payload": None,
                "latest_source_sequence": None,
            },
        )
        source["event_count"] += 1
        latest_sequence = source["latest_source_sequence"]
        if latest_sequence is None or event.source_sequence > latest_sequence:
            mapped = event.to_mapping()
            source.update(
                {
                    "latest_event_id": event.event_id,
                    "latest_event_type": event.event_type,
                    "latest_ingested_at": mapped["ingested_at"],
                    "latest_observed_at": mapped["observed_at"],
                    "latest_payload": deepcopy(dict(event.payload)),
                    "latest_source_sequence": event.source_sequence,
                }
            )

    state: dict[str, Any] = {
        "event_count": event_count,
        "last_ordinal": last_ordinal,
        "projector_version": projector_version,
        "sources": sources,
    }
    canonical = canonical_state_json(state)
    return ProjectionResult(
        state=state,
        canonical_json=canonical,
        state_sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def replay(ledger: EventLedger) -> ProjectionResult:
    """Rebuild current state from the complete append-ordered ledger."""
    return project_events(ledger.read_events())
