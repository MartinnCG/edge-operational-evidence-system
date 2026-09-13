# Architecture boundary

## Current implementation state

M0 establishes repository and package contracts only. It contains no sensor
adapter, event schema, ledger, projector, rule engine or report generator.

The package exposes machine-readable identity metadata so tests can verify that
the repository does not imply runtime capability before implementation exists.

## Intended component boundary

```text
sensor or simulator
        |
        v
protocol adapter -> canonical validation -> append-only event ledger
                                             |
                                             v
                                      deterministic projector
                                             |
                                             v
derived state + quality findings -> rules -> evidence bundle -> report
```

Adapters translate protocols but do not assign operational meaning. The
append-only ledger is the replayable source of truth. State, findings and
reports are versioned projections.

## Approved upstream decisions

The complete system blueprint and architectural decision record are maintained
in the portfolio repository:

- [Foundation blueprint](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/edge_operational_evidence_blueprint.md)
- [ADR-0001: append-only event ledger](https://github.com/MartinnCG/operational-systems-design/blob/main/docs/adr/0001-append-only-event-ledger.md)

## Next decision gate

M1 must define the canonical event envelope and deterministic simulator. It may
not introduce persistence or replay until the event contract has executable
examples, stable validation outcomes and deterministic fixture digests.
