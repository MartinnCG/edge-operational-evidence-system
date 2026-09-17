# ADR-0009: Historical import is a separate evidence boundary

- Status: Accepted
- Date: 2026-09-17
- Milestone: M9A

## Context

A private historical field-derived stream exists from an earlier edge system.
It contains useful longitudinal evidence, but its record shapes, identifiers,
receipt semantics and privacy boundary differ from the public canonical event
contract.

Treating those records as if they had been received live by this repository
would fabricate provenance. Publishing them would also expose deployment
identities and operational context.

## Decision

Historical evidence enters through an explicit import boundary:

1. Exactly two documented source shapes are accepted. Unknown shapes fail
   closed and are counted without echoing their content.
2. Event and source identities are pseudonymised with HMAC-SHA-256 using a
   private key supplied at execution time.
3. A source stream is the original source/channel pair. `source_sequence` is
   derived from accepted input order within that stream.
4. The original observation timestamp is retained.
5. `ingested_at` records historical import time. It does not claim to be the
   unavailable original receipt timestamp.
6. Metadata declares historical-import mode, sequence derivation, source shape,
   source-record digest and archive provenance.
7. Two fresh ledgers independently ingest and replay the mapped stream. Their
   state digests must match.
8. Raw input, pseudonym key and mapped event stream remain private. Only a
   sanitised aggregate result is committed publicly.

## Consequences

- The public repository can demonstrate a tested migration method and report a
  real field-derived qualification without disclosing private evidence.
- Reproduction of pseudonym-dependent digests requires the privately retained
  key and source archive.
- Generic delay findings are not valid measures of historical transport delay,
  because import time replaces an unavailable original receipt time.
- M9A does not prove present-day hardware operation, MQTT transport, mTLS or
  continuity after physical redeployment.

## Rejected alternatives

- Publishing raw records or original identifiers.
- Inventing historical receipt timestamps.
- Deriving pseudonyms from an unkeyed public hash.
- Calling the historical campaign a live 30-day deployment.
