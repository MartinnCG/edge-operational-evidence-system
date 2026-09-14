# Architecture boundary

## Current implementation state

M4 implements a protocol-independent event boundary, deterministic scenarios,
a durable SQLite ledger, versioned replay and generic evidence-quality rules.
It contains no domain rule engine, report generator or hardware adapter.

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
adds transactional, append-only persistence and idempotent retries. M3 projects
that stored truth into canonical per-source state and a reproducible digest.
M4 evaluates explicit evidence conditions without changing ledger or state.

## Approved upstream decisions

The complete system blueprint and architectural decision record are maintained
in the portfolio repository:

- [Foundation blueprint](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/edge_operational_evidence_blueprint.md)
- [ADR-0001: append-only event ledger](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/adr/0001-append-only-event-ledger.md)

## Local decision

- [ADR-0002: SQLite ingestion transactions and idempotency](adr/0002-sqlite-ingestion-transactions.md)
- [ADR-0003: deterministic state projection](adr/0003-deterministic-projection.md)
- [ADR-0004: versioned quality findings](adr/0004-versioned-quality-findings.md)

## Next decision gate

M5 may build evidence bundles only after M4 proves deterministic campaigns and
finding traceability. A bundle must bind source events, projected state, policy,
findings and their exact digests without declaring itself valid before checks run.
