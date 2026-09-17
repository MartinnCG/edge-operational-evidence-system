# Changelog

All notable changes to this project are documented in this file.

The project uses semantic versioning for public releases. Development milestones
describe evidence boundaries and do not imply production certification.

## [Unreleased]

### Added

- A deterministic historical JSONL importer supporting the two documented
  field-record shapes without embedding private source identifiers.
- HMAC pseudonymisation for event and source identities, with the key supplied
  only through an environment variable.
- Explicit historical-import metadata, source-stream sequence derivation and
  provenance digests.
- Independent double-replay qualification and a sanitised M9A aggregate result.
- Synthetic tests covering privacy, both source shapes, deterministic replay,
  key separation, malformed input and duplicate identity handling.

### Security

- Raw telemetry, private keys, canonicalised private output and deployment
  paths remain outside version control.
- Public results withhold pseudonym-key-dependent event and state digests.

### Limitations

- Historical import cannot reconstruct an unavailable original receipt time;
  import time is recorded explicitly and delay metrics must not be interpreted
  as live transport latency.
- M9A does not demonstrate current MQTT, mTLS, hardware or redeployment
  continuity. Those claims remain reserved for a future M9B campaign.

## [0.2.0] - 2026-09-16

### Added

- A concrete Paho MQTT 3.1.1 consumer with callback API v2, manual QoS 1
  acknowledgement and a persistent client session.
- A pinned Eclipse Mosquitto integration fixture proving retained delivery,
  reconnect and resumed durable ingestion after a controlled broker outage.
- Optional mutual-TLS configuration with verified broker identity and mandatory
  client certificates.
- Ephemeral synthetic certificate generation for broker, publisher, consumer,
  health-probe and untrusted-client test identities.
- Certificate-derived Mosquitto identities with separate publish, consume and
  healthcheck ACLs.
- Negative campaigns proving that missing certificates, an untrusted issuer and
  wrong-role publication do not mutate the evidence ledger.
- Dedicated CI jobs for the real-broker and secure-broker campaigns.

### Changed

- The declared implementation boundary advances from M6 to M8.
- Broker health traffic uses a dedicated identity and topic outside the evidence
  hierarchy.
- Repository ignore rules cover generated credentials, local databases,
  evidence outputs, build products and development environments.

### Security

- TLS hostname verification remains enabled in the Paho adapter.
- Generated private keys and certificates are excluded from version control.
- This release proves a local, ephemeral trust boundary; it does not provide
  production PKI lifecycle management, revocation or protected key custody.

## [0.1.0] - 2026-09-15

### Added

- Deterministic canonical event generation and controlled fault scenarios.
- Transactional, append-only and idempotent SQLite ingestion.
- Versioned deterministic replay with canonical state digests.
- Traceable quality findings and reproducible failure campaigns.
- Portable evidence bundles with independent byte and semantic verification.
- A strict MQTT topic/payload adapter and abrupt-process recovery proof.

[0.2.0]: https://github.com/MartinnCG/edge-operational-evidence-system/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/MartinnCG/edge-operational-evidence-system/releases/tag/v0.1.0
