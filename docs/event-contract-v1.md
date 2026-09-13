# Canonical event contract v1.0

## Purpose

The canonical event is the protocol-independent boundary between an adapter or
simulator and future persistence. M1 validates events but does not persist them.

## Required fields

| Field | Type | Rule |
|---|---|---|
| `schema_version` | string | Exactly `1.0`; unsupported versions fail closed |
| `event_id` | string | Stable lowercase identifier, unique per observation |
| `source_id` | string | Synthetic or adapter-assigned source identity |
| `source_sequence` | integer | Non-negative, monotonically increasing at the source |
| `event_type` | string | Version-independent event category |
| `observed_at` | timestamp | RFC 3339 UTC time at the source |
| `ingested_at` | timestamp | RFC 3339 UTC time at the canonical boundary |
| `payload` | object | Event-specific JSON values |
| `metadata` | object | Non-domain context; JSON values only |

Unknown top-level fields are rejected. Numbers must be finite. Ingestion cannot
precede observation. Canonical serialization uses sorted keys, compact
separators, UTF-8, and timestamps normalized to UTC with six fractional digits.

## Ordering semantics

`source_sequence` describes production order for one source. Arrival order is
not silently treated as production order. The M1 stream inspector reports a
`source_sequence_regression` when a new unique event arrives at or below the
highest prior sequence from that source.

## Identity and idempotency boundary

`event_id` is the identity key. M1 detects repeated identities but performs no
write and makes no durability claim. Transactional idempotency begins in M2.

## Time semantics

`observed_at` and `ingested_at` are intentionally distinct. Their difference
supports delayed-arrival findings without rewriting source truth. Both must be
UTC. Clock-quality assessment remains a later concern.

## Evolution policy

- Patch documentation changes do not alter accepted bytes.
- Additive optional fields require a new schema version because v1.0 rejects
  unknown top-level fields.
- Breaking changes require a new major contract version.
- Readers must fail closed on versions they do not implement.

## Claims boundary

Passing validation means only that the record satisfies this software contract.
It does not certify sensor accuracy, source clock accuracy, safety, or domain
suitability.
