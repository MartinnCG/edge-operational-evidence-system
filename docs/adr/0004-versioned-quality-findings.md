# ADR-0004: Versioned and evidence-linked quality findings

- Status: Accepted
- Milestone: M4

## Context

Operational systems often collapse missing, late or repeated evidence into a
single untraceable health label. That makes results difficult to reproduce and
encourages claims stronger than the source evidence supports.

## Decision

Represent each quality observation as a versioned finding linked to immutable
event identities and ledger ordinals. Require an explicit UTC evaluation time
for time-dependent rules. Generate deterministic finding identities from the
rule, source and supporting evidence.

Maintain pre-ledger classifications separately because malformed and duplicate
inputs may never become accepted ledger rows. Run all rules against synthetic,
seeded campaigns before any physical adapter is introduced.

## Consequences

- Findings are reproducible and auditable back to source evidence.
- Rule changes require a new version and may change finding identities.
- Reports can distinguish rejected inputs from accepted-event quality findings.
- Generic indicators do not become domain or safety conclusions accidentally.
- Physical fault validation remains outside M4.
