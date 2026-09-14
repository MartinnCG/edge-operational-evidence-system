# Generic evidence-quality policy v1.0

## Purpose

M4 converts observable evidence conditions into deterministic findings for
human review. A finding is not a diagnosis, safety alarm or instruction to
operate equipment.

## Rules

| Rule | Code | Default | Evidence meaning |
|---|---|---:|---|
| DQ-001 | `delayed_arrival` | >60 s | Receipt lag exceeded policy |
| DQ-002 | `source_sequence_gap` | ≥1 position | Source positions lack evidence |
| DQ-003 | `source_sequence_regression` | any decrease | Arrival order regressed |
| DQ-004 | `repeated_payload_run` | ≥3 events | Identical consecutive payloads |
| DQ-005 | `stale_source` | >60 s | No recent observation at `as_of` |

Thresholds belong to a declared `QualityPolicy`; they are not hidden constants
in a report. Staleness always receives an explicit UTC `as_of` time and never
reads the wall clock implicitly.

## Traceability

Each quality finding contains:

- deterministic SHA-256 `finding_id`;
- code, rule ID and rule version;
- severity and source identity;
- supporting event identities and ledger ordinals;
- machine-readable evidence values;
- bounded interpretation for human review.

The finding identifier binds the rule, source, evidence references and evidence
values. Repeating evaluation against the same inputs and policy returns the same
identifier.

## Boundary findings

Malformed and identical duplicate inputs are identified before persistence.
Campaign reports retain their record index, event identity when available and
boundary-classifier version. Invalid inputs are not inserted into the ledger;
identical retries remain explicit idempotent duplicates.

## Controlled campaigns

The campaign runner covers baseline, delayed, duplicate, reordered, malformed,
missing, stale and frozen synthetic inputs. Identical seed and scenario produce
byte-identical canonical results and the same digest.

## Interpretation boundary

- A sequence gap means evidence is absent, not that an observation never occurred.
- Repeated payloads may be legitimate and do not prove sensor failure.
- Staleness depends on the selected policy and evaluation time.
- Delay does not by itself make payload content false.
- No finding is a safety classification or automated-control command.
