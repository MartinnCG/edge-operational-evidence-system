# Architecture boundary

## Current implementation state

M1 implements a protocol-independent canonical event boundary, deterministic
synthetic scenarios and stateless stream inspection. It contains no durable
ledger, projector, rule engine, report generator or hardware adapter.

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

The simulator and canonical validation boundary are implemented in M1. Stream
inspection demonstrates fault classification without persisting or mutating
events. The ledger remains the planned replayable source of truth.

## Approved upstream decisions

The complete system blueprint and architectural decision record are maintained
in the portfolio repository:

- [Foundation blueprint](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/edge_operational_evidence_blueprint.md)
- [ADR-0001: append-only event ledger](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/adr/0001-append-only-event-ledger.md)

## Next decision gate

M2 may introduce SQLite only after M1 demonstrates stable validation outcomes,
deterministic fixture bytes and explicit ordering semantics. M2 must define the
transaction boundary and prove idempotent ingestion under retries.
