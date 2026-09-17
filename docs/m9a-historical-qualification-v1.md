# M9A Historical Field-Evidence Qualification v1

## Objective

Determine whether a private historical field-derived event stream can cross the
public canonical boundary, enter an append-only ledger and reproduce the same
state in two independent replays without publishing private operational data.

## Evidence scope

- Qualification input: latest cumulative historical JSONL snapshot
- Documented campaign context: 70 canonical daily evidence days across five
  collection windows
- Observation range: 2026-02-13 through 2026-05-25
- Continuity claim: intermittent historical windows, not uninterrupted uptime
- Public data boundary: aggregate results and source digests only

The source archive, original identifiers, pseudonym key, mapped events, exact
deployment paths and pseudonym-dependent state digest remain private.

## Mapping contract

| Historical property | Canonical treatment |
|---|---|
| Original event identity | HMAC pseudonym |
| Source plus sensor/type | HMAC source-stream pseudonym |
| Input order per stream | Derived `source_sequence` |
| `ts` or `ts_utc` | `observed_at` |
| Historical import time | `ingested_at` |
| `signal` | Canonical payload |
| Original schema and quality | Metadata when available |
| Archive and record hashes | Provenance metadata |

No original receipt timestamp is available. The importer records that absence
and does not fabricate one.

## Result

| Measure | Result |
|---|---:|
| Input records | 38,349 |
| Accepted canonical events | 38,349 |
| Rejected records | 0 |
| Primary-v1 records | 38,334 |
| Control-v1 records | 15 |
| Pseudonymised source streams | 6 |
| Independent replay digest match | PASS |

Stable source digests and machine-readable aggregates are recorded in
[`m9a-results-v1.json`](m9a-results-v1.json).

## What this demonstrates

- The historical source shapes are completely recognised by the versioned
  importer used for this run.
- Every record crossed the canonical event contract.
- Pseudonymised identities and derived sequences satisfied ledger uniqueness.
- Two independent ledgers reconstructed an identical final state.
- The public result can be reviewed without receiving raw operational data.

## What this does not demonstrate

- A current physical deployment or uninterrupted 70/90-day availability
- Original message receipt latency
- Sensor calibration, accuracy or safety suitability
- Current MQTT or mTLS transport
- Pack-down and redeployment continuity
- Production security, key custody or device lifecycle management

Those live-system claims remain outside M9A and require a separately executed
M9B campaign.
