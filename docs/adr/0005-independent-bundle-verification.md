# ADR-0005: Independent evidence-bundle verification

- Status: Accepted
- Milestone: M5

## Context

An integrity report generated before validation can incorrectly declare a
bundle valid. Including a mutable verification result inside the same checksum
closure also creates circular or ambiguous trust semantics.

## Decision

Build a fixed, write-once artifact set, then seal payloads and manifest with a
canonical checksum file. Run verification independently and return its result
outside the sealed directory.

Verify semantic relationships in addition to file hashes: finding references,
event content digests, state digest, ordinals, counts, versions and policy.

## Consequences

- Construction and verification are separate operations.
- The report cannot self-certify the bundle.
- Recalculated hashes do not hide internally inconsistent counts or references.
- The complete bundle is portable and contains no absolute runtime paths.
- Authenticity still requires a future external signature or trust anchor.
