# ADR-0006: MQTT authority and controlled restart recovery

- Status: Accepted
- Milestone: M6

## Context

An MQTT adapter can weaken evidence identity if topic and payload both claim the
same fields, if receipt time is producer-controlled, or if redelivery is treated
as a new observation. A graceful close also fails to prove recovery from an
abrupt process termination.

## Decision

Use the versioned topic as the sole authority for source and event type. Accept
an exact JSON payload field set and inject receipt time at the consumer boundary.
Pass the resulting event through the existing canonical validator and durable
ledger. For a committed event identity, retain its original receipt time when a
later byte-equivalent delivery arrives. Record delivery outcomes with
process-local counters.

The controlled campaign writes individual committed events to a WAL-backed
SQLite ledger, terminates the writer with `os._exit(91)`, reopens without cloud
access, redelivers the complete sequence, and compares replay with an
uninterrupted reference digest. It then builds and independently verifies an
evidence bundle from the recovered ledger.

## Consequences

- MQTT-style duplicates converge through ledger idempotency.
- Invalid protocol input cannot bypass the canonical event contract.
- The test crosses a real process boundary and omits graceful database close.
- Recovery remains deterministic and locally reproducible in CI.
- A concrete broker client, broker outage certification, power-loss behavior and
  storage-hardware durability remain outside the claim boundary.
