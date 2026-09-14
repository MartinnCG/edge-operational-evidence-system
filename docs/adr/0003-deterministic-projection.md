# ADR-0003: Deterministic state projection

- Status: Accepted
- Milestone: M3

## Context

Arrival order can vary under imperfect networks even when the logical source
events are identical. A replayable operational system must distinguish append
history from the rule used to select current state.

## Decision

Project immutable ledger rows with projector version `1.0`. Count every accepted
row, but select each source's latest state using its greatest `source_sequence`.
Canonicalize the complete state and calculate SHA-256 over the exact JSON bytes.

Persist optional checkpoints atomically. A checkpoint binds the projector
version, last ledger ordinal, state and digest. Reject incompatible or corrupted
checkpoints rather than attempting repair.

## Consequences

- Repeated replay of one ledger is byte-identical.
- Equivalent event sets produce the same current-state digest despite different
  arrival order.
- Append history remains observable in SQLite and is never rewritten.
- Projection changes must declare a new version.
- The digest demonstrates reproducibility, not authenticity or sensor validity.
