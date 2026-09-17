"""Privacy-preserving qualification of historical operational event streams."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from edge_evidence.event import CanonicalEvent, EventValidationError
from edge_evidence.ledger import EventLedger
from edge_evidence.projection import replay

HISTORICAL_IMPORT_VERSION = "1.0"
_HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_PRIMARY_FIELDS = {
    "event_id",
    "quality",
    "schema_version",
    "sensor",
    "signal",
    "source",
    "ts",
}
_CONTROL_FIELDS = {"event_id", "signal", "source", "ts_utc", "type"}
_NON_IDENTIFIER = re.compile(r"[^a-z0-9._:-]+")


class HistoricalImportError(ValueError):
    """Historical input or configuration cannot be qualified safely."""


@dataclass(frozen=True, slots=True)
class HistoricalImportConfig:
    """Explicit inputs required for a deterministic historical import."""

    pseudonym_key: bytes
    imported_at: datetime
    archive_sha256: str

    def __post_init__(self) -> None:
        if len(self.pseudonym_key) < 16:
            raise HistoricalImportError("pseudonym_key must contain at least 16 bytes")
        if (
            self.imported_at.tzinfo is None
            or self.imported_at.utcoffset() != timedelta(0)
        ):
            raise HistoricalImportError("imported_at must use UTC")
        if not _HEX_DIGEST.fullmatch(self.archive_sha256):
            raise HistoricalImportError(
                "archive_sha256 must be 64 lowercase hex characters"
            )


@dataclass(frozen=True, slots=True)
class HistoricalQualification:
    """Canonical events plus a safe aggregate report."""

    events: tuple[CanonicalEvent, ...]
    report: Mapping[str, Any]


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _pseudonym(key: bytes, prefix: str, value: str, *, length: int = 32) -> str:
    digest = hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}-{digest[:length]}"


def _identifier(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode()
        .lower()
    )
    normalized = _NON_IDENTIFIER.sub("-", normalized).strip("-._:")
    if not normalized:
        raise HistoricalImportError("event type normalizes to an empty identifier")
    return normalized[:128]


def _record_digest(record: Mapping[str, Any]) -> str:
    try:
        canonical = json.dumps(
            record,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise HistoricalImportError("source record is not canonical JSON") from exc
    return hashlib.sha256(canonical.encode()).hexdigest()


def _shape(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    fields = set(record)
    if fields == _PRIMARY_FIELDS:
        return "primary-v1", "ts", "sensor", "sensor"
    if fields == _CONTROL_FIELDS:
        return "control-v1", "ts_utc", "type", "type"
    raise HistoricalImportError("unsupported_record_shape")


def _payload(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {"value": value}


def _map_record(
    record: Mapping[str, Any],
    *,
    config: HistoricalImportConfig,
    sequence: int,
) -> tuple[CanonicalEvent, str]:
    source_format, timestamp_field, type_field, channel_field = _shape(record)
    for field in ("event_id", "source", timestamp_field, type_field):
        if not isinstance(record[field], str) or not record[field]:
            raise HistoricalImportError(f"invalid_{field}")

    source_stream = f"{record['source']}\x00{record[channel_field]}"
    metadata: dict[str, Any] = {
        "historical_import": {
            "archive_sha256": config.archive_sha256,
            "import_version": HISTORICAL_IMPORT_VERSION,
            "ingestion_mode": "historical_import",
            "original_receipt_timestamp_available": False,
            "sequence_basis": "accepted_source_stream_input_order",
            "source_format": source_format,
            "source_record_sha256": _record_digest(record),
        }
    }
    if source_format == "primary-v1":
        metadata["original_schema_version"] = record["schema_version"]
        metadata["original_quality"] = record["quality"]

    mapped = {
        "schema_version": "1.0",
        "event_id": _pseudonym(config.pseudonym_key, "evt", record["event_id"]),
        "source_id": _pseudonym(config.pseudonym_key, "src", source_stream),
        "source_sequence": sequence,
        "event_type": _identifier(record[type_field]),
        "observed_at": record[timestamp_field],
        "ingested_at": _utc(config.imported_at),
        "payload": _payload(record["signal"]),
        "metadata": metadata,
    }
    try:
        return CanonicalEvent.from_mapping(mapped), source_format
    except EventValidationError as exc:
        raise HistoricalImportError(f"canonical_{exc.code}") from exc


def qualify_historical_jsonl(
    path: str | Path, *, config: HistoricalImportConfig
) -> HistoricalQualification:
    """Map a historical JSONL stream and verify two independent replays."""
    source_path = Path(path)
    content = source_path.read_bytes()
    dataset_sha256 = hashlib.sha256(content).hexdigest()
    sequences: dict[str, int] = defaultdict(int)
    seen_event_ids: set[str] = set()
    formats: Counter[str] = Counter()
    rejections: Counter[str] = Counter()
    events: list[CanonicalEvent] = []

    for raw_line in content.splitlines():
        if not raw_line.strip():
            rejections["blank_line"] += 1
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError:
            rejections["invalid_json"] += 1
            continue
        if not isinstance(value, Mapping):
            rejections["non_object"] += 1
            continue
        original_event_id = value.get("event_id")
        if not isinstance(original_event_id, str) or not original_event_id:
            rejections["invalid_event_id"] += 1
            continue
        mapped_event_id = _pseudonym(config.pseudonym_key, "evt", original_event_id)
        if mapped_event_id in seen_event_ids:
            rejections["duplicate_event_id"] += 1
            continue
        try:
            source_format, _, _, channel_field = _shape(value)
            source = value.get("source")
            channel = value.get(channel_field)
            if not isinstance(source, str) or not isinstance(channel, str):
                raise HistoricalImportError("invalid_source_stream")
            source_stream = f"{source}\x00{channel}"
            event, _ = _map_record(
                value,
                config=config,
                sequence=sequences[source_stream],
            )
        except HistoricalImportError as exc:
            rejections[str(exc)] += 1
            continue
        seen_event_ids.add(event.event_id)
        sequences[source_stream] += 1
        formats[source_format] += 1
        events.append(event)

    first_state_sha256 = _replay_digest(events)
    second_state_sha256 = _replay_digest(events)
    if first_state_sha256 != second_state_sha256:
        raise HistoricalImportError("independent replay digests differ")

    canonical_bytes = b"".join(
        (event.canonical_json() + "\n").encode() for event in events
    )
    observations = [event.observed_at for event in events]
    report = {
        "archive_sha256": config.archive_sha256,
        "canonical_events_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "dataset_sha256": dataset_sha256,
        "event_count": len(events),
        "first_observed_at": _utc(min(observations)) if observations else None,
        "format_counts": dict(sorted(formats.items())),
        "import_version": HISTORICAL_IMPORT_VERSION,
        "imported_at": _utc(config.imported_at),
        "independent_replay_match": True,
        "last_observed_at": _utc(max(observations)) if observations else None,
        "rejection_counts": dict(sorted(rejections.items())),
        "rejection_count": sum(rejections.values()),
        "source_count": len(sequences),
        "state_sha256": first_state_sha256,
    }
    return HistoricalQualification(tuple(events), report)


def _replay_digest(events: Sequence[CanonicalEvent]) -> str:
    with EventLedger(":memory:") as ledger:
        ledger.ingest_many(events)
        return replay(ledger).state_sha256


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be RFC 3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("timestamp must use UTC")
    return parsed.astimezone(UTC)


def _write_new(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except FileExistsError as exc:
        raise HistoricalImportError(f"output already exists: {path}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Qualify and pseudonymize a historical operational JSONL stream."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--imported-at", type=_parse_utc, required=True)
    parser.add_argument(
        "--key-env",
        default="EDGE_EVIDENCE_IMPORT_KEY",
        help="environment variable containing the private pseudonym key",
    )
    args = parser.parse_args(argv)
    key = os.environ.get(args.key_env)
    if key is None:
        parser.error(f"required environment variable is not set: {args.key_env}")
    qualification = qualify_historical_jsonl(
        args.input,
        config=HistoricalImportConfig(
            pseudonym_key=key.encode(),
            imported_at=args.imported_at,
            archive_sha256=args.archive_sha256,
        ),
    )
    events_bytes = b"".join(
        (event.canonical_json() + "\n").encode() for event in qualification.events
    )
    report_bytes = (
        json.dumps(qualification.report, indent=2, sort_keys=True) + "\n"
    ).encode()
    _write_new(args.events_output, events_bytes)
    _write_new(args.report_output, report_bytes)
    print(json.dumps(qualification.report, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
