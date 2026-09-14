# Operational evidence-bundle contract v1.0

## Purpose

An evidence bundle is a portable, write-once directory that binds accepted
events, reconstructed state, quality observations, policy and a human-readable
report. It supports independent reproducibility checks without a cloud service.

## Canonical file set

| Artifact | Purpose |
|---|---|
| `ledger_events.jsonl` | Ordinal, event content digest and canonical event |
| `state.json` | Canonical projected state |
| `quality_findings.jsonl` | Versioned findings linked to ledger evidence |
| `boundary_findings.jsonl` | Invalid/duplicate pre-ledger classifications |
| `policy.json` | Exact quality-policy version and thresholds |
| `run.json` | Bundle identity, explicit times, versions and counts |
| `report.md` | Bounded human-readable summary |
| `manifest.json` | Size, media type and SHA-256 for every payload artifact |
| `checksums.sha256` | SHA-256 for every payload artifact and the manifest |

Missing and additional files both invalidate the bundle contract. Paths are
relative and flat so no local machine path enters the evidence.

## Construction order

1. Read and verify immutable ledger rows.
2. Reconstruct canonical state.
3. Evaluate quality using an explicit UTC `as_of` time.
4. Write payload artifacts inside a new temporary directory.
5. Hash payload bytes and write the manifest.
6. Hash payloads plus manifest and write `checksums.sha256`.
7. Atomically rename the completed directory to its final write-once target.

The builder refuses to replace an existing target.

## Independent verification

Verification runs after construction and does not write into the sealed bundle.
It checks:

- exact file-set and canonical checksum syntax;
- checksum and manifest hashes, sizes and media types;
- canonical JSON and JSONL encoding;
- canonical event validity and stored event content digest;
- strictly increasing ledger ordinals;
- quality-finding identities and event/ordinal references;
- run counts, component versions and bundle identity;
- state digest, event count and last ordinal;
- quality-policy structure and version.

A checksum-correct but semantically inconsistent bundle still fails.

## Report boundary

The report describes counts and evidence-condition codes. At construction time
it states `Bundle sealed; independent verification required.` It never treats
its own presence as proof of validity.

## Trust boundary

SHA-256 detects accidental or uncoordinated alteration and demonstrates
reproducibility. M5 does not include a digital signature, trusted timestamp,
external identity, archival guarantee, sensor certification or safety approval.
An actor able to replace every artifact and every hash can forge a new unsigned
bundle; external signing is a possible later extension.
