# Edge Operational Evidence System

[![Quality gate](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml/badge.svg)](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml)

Edge-first reference system for reproducible, traceable operational evidence
under imperfect sensors and networks.

**Current phase:** M2 — durable, idempotent SQLite event ledger  
**Implemented capability:** synthetic event generation, canonical validation,
stateless stream inspection and transactional append-only persistence

## Demonstrated through M2

- a strict versioned event envelope;
- byte-identical JSONL for identical seed and configuration;
- separate observation and ingestion timestamps;
- machine-readable rejection reasons;
- synthetic baseline, delayed, duplicate, reordered and malformed scenarios;
- stateless classification of those four fault conditions.
- transactional SQLite ingestion with stable append ordinals;
- idempotent retries and fail-closed identity conflicts;
- atomic batch rollback and database-level mutation prevention;
- durable content and digest recovery after reopening the database.

M2 does **not** claim deterministic replay, derived-state recovery, sensor
accuracy or evidence-bundle integrity.

## Quick start

Requires Python 3.11 or 3.12.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

Generate a deterministic baseline:

```bash
edge-evidence-simulate --seed 2026 --count 8 --output baseline.jsonl
sha256sum baseline.jsonl
```

Generate a controlled fault fixture:

```bash
edge-evidence-simulate --scenario reordered --count 8
```

The command emits synthetic data only. See the executable contract in
[`docs/event-contract-v1.md`](docs/event-contract-v1.md).

## Mission

Build a public, reproducible reference system that preserves and reconstructs
operational evidence at the edge when sensors, networks and processes are
imperfect.

The system is designed to answer what was observed, when it was observed and
received, how it was qualified, what state was derived, and whether that result
can be reproduced after restart.

## Core invariants

1. Accepted canonical events are append-only.
2. Reprocessing an event is idempotent.
3. Replay under the same version produces the same state digest.
4. Observation and receipt times remain distinct.
5. Restart recovery does not require cloud access.
6. Missing, stale, frozen and invalid evidence remains explicit.
7. Interpretation components declare their versions.
8. Findings support human review and do not control physical equipment.

Only invariant 4 and the explicit treatment of invalid, delayed, duplicate and
reordered inputs were implemented in M1. M2 implements append-only persistence
and idempotent ingestion. Replay and restart-state invariants remain requirements.

## Delivery sequence

| Milestone | Evidence target |
|---|---|
| M0 | Installable package, repository contract, tests and CI |
| M1 | Deterministic simulator and versioned event contract |
| M2 | Durable, transactional and idempotent SQLite ledger |
| M3 | Deterministic state reconstruction and state digest |
| M4 | Traceable data-quality findings and failure fixtures |
| M5 | Reproducible evidence bundle and operational report |
| M6 | MQTT adapter and controlled offline/restart campaign |

## Architecture

The approved blueprint and first architecture decision are maintained in
[Operational Systems Design](https://github.com/MartinnCG/operational-systems-design).
The repository-level boundary is recorded in
[`docs/architecture.md`](docs/architecture.md).
SQLite transaction and idempotency choices are recorded in
[`ADR-0002`](docs/adr/0002-sqlite-ingestion-transactions.md).

## Claims and data boundary

This repository is an engineering reference implementation. It does not certify
sensor accuracy, operational safety or domain suitability. Public examples use
synthetic identities, locations and measurements only. Findings are evidence
for human review, not instructions to operate equipment.

## License

No open-source licence has been selected yet. Until one is added, the repository
is publicly viewable but reuse rights are not granted.
