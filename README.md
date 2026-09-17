# Edge Operational Evidence System

[![Quality gate](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml/badge.svg)](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml)

Edge-first reference system for reproducible, traceable operational evidence
under imperfect sensors and networks.

**Current phase:** M8 — mutual-TLS identity and MQTT authorization  
**Current release:** v0.2.0  
**Implemented capability:** synthetic event generation, canonical validation,
durable ingestion, versioned replay, quality campaigns, portable bundles and
real-broker integration proof

## Demonstrated through M8

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
- a concrete Paho 2.x consumer using callback API v2 and manual QoS 1 ACK;
- a pinned, loopback-only Eclipse Mosquitto container;
- retained-message delivery to a fresh subscriber;
- controlled broker stop/start with automatic client reconnection;
- resumed durable ingestion after the broker becomes available again.
- ephemeral synthetic certificate-authority and role identities;
- TLS with broker hostname verification and mandatory client certificates;
- certificate Common Name mapped to Mosquitto authorization identity;
- separate publish and consume ACL permissions;
- negative anonymous, untrusted-certificate and wrong-role campaigns;
- proof that unauthorized publication does not mutate the evidence ledger.

M8 does **not** claim production PKI, certificate rotation or revocation,
hardware-backed keys, enterprise identity integration, end-to-end availability,
sensor accuracy or safety-critical suitability.

## Quick start

Requires Python 3.11 or 3.12.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev,mqtt]"
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

Run the opt-in real-broker campaign:

```bash
docker compose -f ops/mqtt/compose.yml up -d --wait
MQTT_INTEGRATION=1 python -m pytest \
  tests/test_mqtt_integration.py -m integration
docker compose -f ops/mqtt/compose.yml down --volumes
```

Run the opt-in mutual-TLS and authorization campaign:

```bash
sh ops/mqtt-secure/generate-test-pki.sh
docker compose -f ops/mqtt-secure/compose.yml up -d --wait
MQTT_SECURITY_INTEGRATION=1 python -m pytest \
  tests/test_mqtt_security_integration.py -m integration
docker compose -f ops/mqtt-secure/compose.yml down --volumes
```

Qualify a private historical JSONL stream without publishing its identities:

```bash
export EDGE_EVIDENCE_IMPORT_KEY='<private value of at least 16 bytes>'
edge-evidence-historical \
  --input /outside-the-repository/events.jsonl \
  --events-output /outside-the-repository/events.canonical.jsonl \
  --report-output /outside-the-repository/qualification.private.json \
  --archive-sha256 <source-archive-sha256> \
  --imported-at 2026-09-17T00:00:00Z
```

The private key, original stream and canonical output must remain outside the
repository. The public M9A result contains aggregate counts and stable source
digests only.

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
M7 connects that boundary to a pinned Mosquitto broker through Paho, then proves
retained QoS 1 delivery and recovery from a controlled broker outage.
M8 adds mutual-TLS identity and role-based authorization, including negative
campaigns that prove unauthorized inputs cannot reach the evidence ledger.

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
| M7 | Real Mosquitto/Paho integration and reconnect campaign |
| M8 | Mutual-TLS identity and per-client authorization campaign |
| M9A | Historical field-evidence qualification and deterministic replay |
| M9B | Future live redeployment continuity campaign; not yet executed |

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
The real-broker decision and campaign are documented in
[`ADR-0007`](docs/adr/0007-real-mqtt-integration.md) and
[`mqtt-integration-campaign-v1.md`](docs/mqtt-integration-campaign-v1.md).
The secure boundary is recorded in
[`ADR-0008`](docs/adr/0008-mutual-tls-and-authorization.md) and
[`mqtt-security-campaign-v1.md`](docs/mqtt-security-campaign-v1.md).
The historical-import boundary and sanitised result are recorded in
[`ADR-0009`](docs/adr/0009-historical-import-boundary.md) and
[`m9a-historical-qualification-v1.md`](docs/m9a-historical-qualification-v1.md).

Release history is maintained in [`CHANGELOG.md`](CHANGELOG.md). The verified
v0.2.0 boundary is summarized in
[`docs/releases/v0.2.0.md`](docs/releases/v0.2.0.md).

## Claims and data boundary

This repository is an engineering reference implementation. It does not certify
sensor accuracy, operational safety or domain suitability. Public examples use
synthetic identities, locations and measurements only. Findings are evidence
for human review, not instructions to operate equipment.

## License

No open-source licence has been selected yet. Until one is added, the repository
is publicly viewable but reuse rights are not granted.
