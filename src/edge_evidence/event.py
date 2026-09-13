"""Canonical event contract and deterministic JSON representation."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1.0"
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_FIELDS = {
    "schema_version",
    "event_id",
    "source_id",
    "source_sequence",
    "event_type",
    "observed_at",
    "ingested_at",
    "payload",
    "metadata",
}


class EventValidationError(ValueError):
    """A contract rejection with a stable machine-readable reason."""

    def __init__(self, code: str, field: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.field = field


def _reject(code: str, field: str, message: str) -> None:
    raise EventValidationError(code, field, message)


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        _reject("invalid_type", field, f"{field} must be a UTC timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject("invalid_timestamp", field, f"{field} is not valid RFC 3339")
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        _reject("timestamp_not_utc", field, f"{field} must use UTC")
    return parsed.astimezone(UTC)


def _format_utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _validate_json(value: Any, field: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            _reject("non_finite_number", field, f"{field} contains a non-finite number")
        return
    if isinstance(value, list):
        for item in value:
            _validate_json(item, field)
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _reject("invalid_json_key", field, f"{field} keys must be strings")
            _validate_json(item, field)
        return
    _reject("invalid_json_value", field, f"{field} contains a non-JSON value")


@dataclass(frozen=True, slots=True)
class CanonicalEvent:
    """Version 1.0 event accepted at the protocol-independent boundary."""

    event_id: str
    source_id: str
    source_sequence: int
    event_type: str
    observed_at: datetime
    ingested_at: datetime
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any]
    schema_version: str = SCHEMA_VERSION

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> CanonicalEvent:
        if not isinstance(record, Mapping):
            _reject("invalid_record", "$", "event must be an object")
        missing = _FIELDS - record.keys()
        if missing:
            field = sorted(missing)[0]
            _reject("missing_field", field, f"missing required field: {field}")
        unknown = record.keys() - _FIELDS
        if unknown:
            field = sorted(unknown)[0]
            _reject("unknown_field", field, f"unknown field: {field}")
        if record["schema_version"] != SCHEMA_VERSION:
            _reject(
                "unsupported_schema_version",
                "schema_version",
                f"supported schema version is {SCHEMA_VERSION}",
            )
        for field in ("event_id", "source_id", "event_type"):
            value = record[field]
            if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
                _reject("invalid_identifier", field, f"invalid {field}")
        sequence = record["source_sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            _reject(
                "invalid_source_sequence",
                "source_sequence",
                "source_sequence must be a non-negative integer",
            )
        for field in ("payload", "metadata"):
            value = record[field]
            if not isinstance(value, Mapping):
                _reject("invalid_type", field, f"{field} must be an object")
            _validate_json(value, field)
        observed = _parse_utc(record["observed_at"], "observed_at")
        ingested = _parse_utc(record["ingested_at"], "ingested_at")
        if ingested < observed:
            _reject(
                "ingestion_before_observation",
                "ingested_at",
                "ingested_at cannot precede observed_at",
            )
        return cls(
            schema_version=SCHEMA_VERSION,
            event_id=record["event_id"],
            source_id=record["source_id"],
            source_sequence=sequence,
            event_type=record["event_type"],
            observed_at=observed,
            ingested_at=ingested,
            payload=dict(record["payload"]),
            metadata=dict(record["metadata"]),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "ingested_at": _format_utc(self.ingested_at),
            "metadata": dict(self.metadata),
            "observed_at": _format_utc(self.observed_at),
            "payload": dict(self.payload),
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_sequence": self.source_sequence,
        }

    def canonical_json(self) -> str:
        return json.dumps(
            self.to_mapping(),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
