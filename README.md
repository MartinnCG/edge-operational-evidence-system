# Edge Operational Evidence System

[![Quality gate](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml/badge.svg)](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml)

Edge-first reference system for reproducible, traceable operational evidence
under imperfect sensors and networks.

**Current phase:** M6 — MQTT boundary and controlled restart recovery  
**Implemented capability:** synthetic event generation, canonical validation,
durable ingestion, versioned replay, quality campaigns, portable bundles and
process-level recovery proof

## Demonstrated through M6

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
- deterministic reconstruction of versioned per-source state;
- arrival-order-independent current state using source sequence;
- canonical state bytes and SHA-256 digest;
- atomic checkpoints that fail closed on corruption or version mismatch.
- versioned findings linked to event identities and ledger ordinals;
- explicit delay, gap, regression, repeated-payload and stale-source indicators;
- deterministic baseline and seven synthetic failure campaigns;
- canonical campaign outputs and reproducible SHA-256 digests.
- write-once bundles constructed through atomic directory publication;
- manifests binding artifact paths, sizes, media types and SHA-256 digests;
- semantic verification of event, state, policy and finding relationships;
- deterministic human-readable reports with explicit claim boundaries.
- a strict, versioned MQTT topic/payload mapping into canonical events;
- fail-closed protocol rejection and observable delivery counters;
- idempotent convergence after MQTT-style redelivery;
- committed SQLite recovery after abrupt process termination;
- digest equality with an uninterrupted reference execution;
- independent verification of the recovered evidence bundle.

M6 does **not** claim broker certification, end-to-end network reliability,
digital-signature authenticity, sensor accuracy, safety diagnosis, long-term
archival guarantees or physical fault survivability.

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

Run a complete quality campaign:

```bash
edge-evidence-campaign missing --output missing-campaign.json
```

Build and independently verify a synthetic evidence bundle:

```bash
edge-evidence-bundle build-demo missing \
  --output evidence/demo-missing \
  --bundle-id demo-missing-001 \
  --created-at 2026-01-02T03:04:05Z
edge-evidence-bundle verify evidence/demo-missing
```

Run the process-level recovery proof:

```bash
edge-evidence-recovery run \
  --workspace evidence/m6-recovery \
  --count 8 \
  --crash-after 4
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
and idempotent ingestion. M3 implements deterministic replay and state digests.
M4 adds generic, traceable quality findings. M5 seals these layers into portable
bundles and verifies their bytes and semantic cross-references independently.
M6 maps MQTT deliveries into the canonical boundary and proves local recovery,
redelivery convergence and evidence verification after abrupt process exit.

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
Projection ordering and versioning are recorded in
[`ADR-0003`](docs/adr/0003-deterministic-projection.md).
Quality traceability is recorded in
[`ADR-0004`](docs/adr/0004-versioned-quality-findings.md).
Bundle trust and verification are recorded in
[`ADR-0005`](docs/adr/0005-independent-bundle-verification.md).
MQTT authority and restart recovery are recorded in
[`ADR-0006`](docs/adr/0006-mqtt-boundary-and-recovery.md).
The executable message and campaign contracts are documented in
[`mqtt-boundary-v1.md`](docs/mqtt-boundary-v1.md) and
[`recovery-campaign-v1.md`](docs/recovery-campaign-v1.md).

## Claims and data boundary

This repository is an engineering reference implementation. It does not certify
sensor accuracy, operational safety or domain suitability. Public examples use
synthetic identities, locations and measurements only. Findings are evidence
for human review, not instructions to operate equipment.

## License

No open-source licence has been selected yet. Until one is added, the repository
is publicly viewable but reuse rights are not granted.
