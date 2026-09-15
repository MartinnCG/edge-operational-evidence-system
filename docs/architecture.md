# Architecture boundary

## Current implementation state

M8 implements a protocol-independent event boundary, deterministic scenarios,
a durable SQLite ledger, versioned replay, generic quality rules, portable
evidence bundles, a strict MQTT message adapter and a concrete Paho client tested
against a pinned Mosquitto container. It contains no domain rule engine or
hardware-specific adapter.

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
M5 binds those layers into a write-once artifact set and verifies it in a
separate operation.
M6 proves MQTT-style redelivery and restart recovery through the same boundaries.
M7 adds a real broker transport without changing canonical evidence semantics.
M8 authenticates synthetic client identities with TLS certificates and limits
their broker permissions before evidence reaches the M6 boundary.

## Approved upstream decisions

The complete system blueprint and architectural decision record are maintained
in the portfolio repository:

- [Foundation blueprint](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/edge_operational_evidence_blueprint.md)
- [ADR-0001: append-only event ledger](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/adr/0001-append-only-event-ledger.md)

## Local decision

- [ADR-0002: SQLite ingestion transactions and idempotency](adr/0002-sqlite-ingestion-transactions.md)
- [ADR-0003: deterministic state projection](adr/0003-deterministic-projection.md)
- [ADR-0004: versioned quality findings](adr/0004-versioned-quality-findings.md)
- [ADR-0005: independent bundle verification](adr/0005-independent-bundle-verification.md)
- [ADR-0006: MQTT boundary and controlled recovery](adr/0006-mqtt-boundary-and-recovery.md)
- [ADR-0007: real MQTT integration](adr/0007-real-mqtt-integration.md)
- [ADR-0008: mutual TLS and authorization](adr/0008-mutual-tls-and-authorization.md)

## v0.1 boundary

M0–M6 form the v0.1 reference path. M7 begins v0.2 development by adding a
concrete broker client and reproducible integration environment. M8 adds a
controlled certificate trust and authorization boundary. A later milestone may
add external signatures or a hardware campaign only with explicit contracts and
without weakening the evidence layers.
