# Deterministic projector contract v1.0

## Purpose

Projector v1.0 reconstructs a compact operational state from immutable ledger
rows. The result is derived evidence: the ledger remains the source of truth.

## State structure

The canonical state contains:

- `projector_version`: exactly `1.0`;
- `event_count`: number of applied ledger rows;
- `last_ordinal`: highest applied append ordinal, or zero for an empty ledger;
- `sources`: object keyed by source identity.

Each source contains its applied event count and the identity, type, timestamps,
payload and source sequence of the event with the greatest source sequence.

## Ordering decision

Ledger rows are read in append order and their ordinals must increase strictly.
The latest state for a source is selected by `source_sequence`, not arrival
order. Therefore, the same logical event set produces the same state if network
delay changes arrival order.

M3 does not erase or reorder the source ledger. It changes only how current
derived state is selected.

## Canonical bytes and digest

State is encoded as UTF-8 JSON with sorted keys, compact separators, finite
numbers and no insignificant whitespace. SHA-256 is calculated over those exact
bytes.

The digest proves repeatability and detects accidental change. It is not a
signature, proof of sensor accuracy or protection against an administrator who
can replace both state and digest.

## Checkpoint contract

A checkpoint binds:

- checkpoint version;
- projector version;
- last applied ordinal;
- complete canonical state;
- state SHA-256 digest.

Checkpoint writes use a temporary file, file synchronization and atomic rename.
Loading fails closed on malformed JSON, unexpected fields, unsupported versions,
ordinal mismatch, projector mismatch or digest mismatch.

## Versioning

Any change capable of altering projected state bytes requires a new projector
version. Old checkpoints must never be interpreted using new projection rules.
