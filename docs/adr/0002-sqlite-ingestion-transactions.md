# ADR-0002: SQLite ingestion transactions and idempotency

- Status: Accepted
- Milestone: M2

## Context

Edge ingestion must survive retries without silently accepting conflicting
identity claims. The ledger must remain usable without network or cloud access,
and committed events must not be edited retroactively.

## Decision

Use SQLite as the initial durable event ledger with these rules:

1. A write begins with `BEGIN IMMEDIATE`, so competing writers are serialized
   before identity checks and insertion.
2. `event_id` is unique. Byte-equivalent canonical content is an idempotent
   duplicate; different content under the same identity is a conflict.
3. `(source_id, source_sequence)` is unique. A second event identity cannot
   claim an existing source position.
4. Batch ingestion occurs in one transaction. Any conflict rolls back the
   complete batch.
5. Database triggers reject `UPDATE` and `DELETE` against the event table.
6. Every row stores canonical JSON and its SHA-256 digest.
7. Append order is the database-assigned integer `ordinal`, not observation or
   ingestion time.

## SQLite policy

- `journal_mode=WAL` for file-backed databases;
- `synchronous=FULL` to wait for durable synchronization at commit;
- `busy_timeout=5000` milliseconds by default for local writer contention;
- `foreign_keys=ON` for forward-compatible schema discipline.

These settings reduce, but do not eliminate, storage and operating-system
failure risks. They are not a substitute for backup or filesystem integrity.

## Consequences

- Identical retries do not create new rows.
- Identity ambiguity fails closed and remains visible to the caller.
- Multiple local writers can contend safely within the configured timeout.
- Append-only triggers prevent ordinary mutation through SQL, but a database
  administrator can still alter schema or files outside the application.
- The ledger does not yet prove replay equivalence or state correctness; those
  claims belong to M3.
