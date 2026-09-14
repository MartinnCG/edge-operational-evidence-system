"""Durable, transactional and append-only SQLite event ledger."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from edge_evidence.event import CanonicalEvent

LEDGER_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_metadata (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    schema_version INTEGER NOT NULL
);

INSERT OR IGNORE INTO ledger_metadata (singleton, schema_version) VALUES (1, 1);

CREATE TABLE IF NOT EXISTS events (
    ordinal INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    source_id TEXT NOT NULL,
    source_sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    UNIQUE (source_id, source_sequence)
);

CREATE TRIGGER IF NOT EXISTS events_prevent_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: update rejected');
END;

CREATE TRIGGER IF NOT EXISTS events_prevent_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: delete rejected');
END;
"""


class IngestStatus(StrEnum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"


class LedgerConflictError(RuntimeError):
    """Base class for an identity conflict that fails closed."""


class EventIdentityConflict(LedgerConflictError):
    """The event identity already binds different canonical content."""


class SourceSequenceConflict(LedgerConflictError):
    """A source sequence already binds another event identity."""


class LedgerIntegrityError(RuntimeError):
    """Stored canonical content no longer matches its recorded digest."""


@dataclass(frozen=True, slots=True)
class IngestResult:
    status: IngestStatus
    event_id: str
    ordinal: int
    content_sha256: str


@dataclass(frozen=True, slots=True)
class StoredEvent:
    ordinal: int
    event: CanonicalEvent
    content_sha256: str


class EventLedger:
    """One SQLite connection with explicit transaction and durability policy."""

    def __init__(self, path: str | Path, *, timeout_seconds: float = 5.0) -> None:
        self.path = str(path)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            timeout=timeout_seconds,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._configure(timeout_seconds)
        self._initialize_schema()

    def _configure(self, timeout_seconds: float) -> None:
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA synchronous = FULL")

    def _initialize_schema(self) -> None:
        with self._lock:
            self._connection.executescript(_SCHEMA)
            row = self._connection.execute(
                "SELECT schema_version FROM ledger_metadata WHERE singleton = 1"
            ).fetchone()
            if row is None or row["schema_version"] != LEDGER_SCHEMA_VERSION:
                raise RuntimeError("unsupported ledger schema version")

    @staticmethod
    def _coerce(record: CanonicalEvent | Mapping[str, Any]) -> CanonicalEvent:
        if isinstance(record, CanonicalEvent):
            return record
        return CanonicalEvent.from_mapping(record)

    @staticmethod
    def _content(event: CanonicalEvent) -> tuple[str, str]:
        canonical = event.canonical_json()
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        return canonical, digest

    def _ingest_in_transaction(self, event: CanonicalEvent) -> IngestResult:
        canonical, digest = self._content(event)
        existing = self._connection.execute(
            """
            SELECT ordinal, canonical_json, content_sha256
            FROM events WHERE event_id = ?
            """,
            (event.event_id,),
        ).fetchone()
        if existing is not None:
            if existing["canonical_json"] == canonical:
                return IngestResult(
                    IngestStatus.DUPLICATE,
                    event.event_id,
                    existing["ordinal"],
                    existing["content_sha256"],
                )
            raise EventIdentityConflict(
                f"event_id {event.event_id!r} already binds different content"
            )

        sequence_owner = self._connection.execute(
            """
            SELECT event_id FROM events
            WHERE source_id = ? AND source_sequence = ?
            """,
            (event.source_id, event.source_sequence),
        ).fetchone()
        if sequence_owner is not None:
            raise SourceSequenceConflict(
                f"source sequence already belongs to {sequence_owner['event_id']!r}"
            )

        cursor = self._connection.execute(
            """
            INSERT INTO events (
                event_id, source_id, source_sequence, event_type,
                observed_at, ingested_at, schema_version,
                canonical_json, content_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.source_id,
                event.source_sequence,
                event.event_type,
                event.to_mapping()["observed_at"],
                event.to_mapping()["ingested_at"],
                event.schema_version,
                canonical,
                digest,
            ),
        )
        return IngestResult(
            IngestStatus.ACCEPTED, event.event_id, cursor.lastrowid, digest
        )

    def ingest(
        self, record: CanonicalEvent | Mapping[str, Any]
    ) -> IngestResult:
        return self.ingest_many((record,))[0]

    def ingest_many(
        self, records: Iterable[CanonicalEvent | Mapping[str, Any]]
    ) -> tuple[IngestResult, ...]:
        """Commit every record atomically or roll back the complete batch."""
        events = tuple(self._coerce(record) for record in records)
        if not events:
            return ()
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                results = tuple(
                    self._ingest_in_transaction(event) for event in events
                )
                self._connection.execute("COMMIT")
                return results
            except BaseException:
                if self._connection.in_transaction:
                    self._connection.execute("ROLLBACK")
                raise

    def count(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS n FROM events"
            ).fetchone()
            return int(row["n"])

    def read_events(self) -> tuple[StoredEvent, ...]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT ordinal, canonical_json, content_sha256
                FROM events ORDER BY ordinal ASC
                """
            ).fetchall()
        stored: list[StoredEvent] = []
        for row in rows:
            actual_digest = hashlib.sha256(row["canonical_json"].encode()).hexdigest()
            if actual_digest != row["content_sha256"]:
                raise LedgerIntegrityError(
                    f"content digest mismatch at ordinal {row['ordinal']}"
                )
            stored.append(
                StoredEvent(
                    ordinal=row["ordinal"],
                    event=CanonicalEvent.from_mapping(json.loads(row["canonical_json"])),
                    content_sha256=row["content_sha256"],
                )
            )
        return tuple(stored)

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
