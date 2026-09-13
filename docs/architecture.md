# Architecture boundary

## Current implementation state

M2 implements a protocol-independent canonical event boundary, deterministic
synthetic scenarios, stateless stream inspection and a durable SQLite ledger.
It contains no projector, replay engine, rule engine, report generator or
hardware adapter.

## Intended component boundary

```text
sensor or simulator
        |
        v
protocol adapter -> canonical validation -> append-only event ledger
                                             |
                                             v
                                      deterministic projector
                                             |
                                             v
derived state + quality findings -> rules -> evidence bundle -> report
```

The simulator and canonical validation boundary were implemented in M1. M2
adds transactional, append-only persistence and idempotent retries. The ledger
is now the stored source of truth, but deterministic state replay is not yet
implemented.

## Approved upstream decisions

The complete system blueprint and architectural decision record are maintained
in the portfolio repository:

- [Foundation blueprint](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/edge_operational_evidence_blueprint.md)
- [ADR-0001: append-only event ledger](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/adr/0001-append-only-event-ledger.md)

## Local decision

- [ADR-0002: SQLite ingestion transactions and idempotency](adr/0002-sqlite-ingestion-transactions.md)

## Next decision gate

M3 may introduce projectors only after M2 proves atomic writes, retry
idempotency, conflict rollback, append-order reads and persistence across reopen.
M3 must define projector versioning and a canonical state digest.
