# Edge Operational Evidence System

[![Quality gate](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml/badge.svg)](https://github.com/MartinnCG/edge-operational-evidence-system/actions/workflows/quality.yml)

Edge-first reference system for reproducible, traceable operational evidence
under imperfect sensors and networks.

**Current phase:** M0 — repository contract  
**Runtime capability:** not implemented

## Mission

Build a public, reproducible reference system that preserves and reconstructs
operational evidence at the edge when sensors, networks and processes are
imperfect.

The system is designed to answer:

- What was observed?
- When was it observed and received?
- Was the observation accepted, rejected or qualified?
- What state was derived from the available evidence?
- Which rule produced a finding?
- Can the result be reproduced after a restart?

## v0.1 boundary

### In scope

- deterministic sensor and fault simulation;
- canonical event validation;
- append-only local event persistence;
- idempotent ingestion;
- deterministic state reconstruction;
- explicit data-quality findings;
- rule evaluation over derived state;
- structured evidence bundles;
- health metrics and human-readable reports;
- automated failure campaigns.

### Out of scope

- direct actuator or equipment control;
- safety-certified alarms or decisions;
- cloud availability as a core dependency;
- machine-learning prediction;
- autonomous agents;
- customer dashboards;
- real client, property, employee or mine-site data.

## Core invariants

1. Accepted canonical events are append-only.
2. Reprocessing an event is idempotent.
3. Replay under the same version produces the same state digest.
4. Observation and receipt times remain distinct.
5. Restart recovery does not require cloud access.
6. Missing, stale, frozen and invalid evidence remains explicit.
7. Interpretation components declare their versions.
8. Findings support human review and do not control physical equipment.

These are architectural requirements. M0 does not claim that they have already
been implemented.

## Architecture

The approved blueprint and first architecture decision are maintained in
[Operational Systems Design](https://github.com/MartinnCG/operational-systems-design):

- [Foundation blueprint](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/edge_operational_evidence_blueprint.md)
- [ADR-0001: append-only event ledger](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/adr/0001-append-only-event-ledger.md)

A local repository-level architecture boundary is recorded in
[`docs/architecture.md`](docs/architecture.md).

## Development setup

Requires Python 3.11 or 3.12.

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
```

The package currently exposes identity and development-version metadata only.
Event contracts and runtime behaviour begin in M1.

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

## Claims boundary

This repository is an engineering reference implementation. It does not
certify sensor accuracy, operational safety or domain suitability. Public
examples use synthetic data only. Findings are evidence for human review, not
instructions to operate equipment.

## License

No open-source licence has been selected yet. Until one is added, the repository
is publicly viewable but reuse rights are not granted.
