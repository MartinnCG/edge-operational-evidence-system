# Contributing

Contributions should produce verifiable engineering evidence rather than
activity for its own sake.

## Workflow

1. Open or select an issue with acceptance criteria and explicit non-goals.
2. Create a focused branch.
3. Make atomic commits that describe engineering outcomes.
4. Run:
   ```bash
   python -m pip install -e ".[dev]"
   python -m ruff check .
   python -m pytest
   ```
5. Open a pull request using the repository template.
6. Do not merge while a quality gate is failing.

## Evidence requirements

A material pull request should explain:

- the observable problem;
- the system boundary;
- the implementation decision;
- verification that matches the claim;
- limitations and follow-up risks;
- any data-provenance or sensitivity implications.

## Public-data policy

Use synthetic data by default. Do not commit credentials, personal information,
client material, precise private-site locations or operational documents
without explicit authorization and a documented reason.

## Scope discipline

M0 contains repository infrastructure only. Do not introduce event, sensor,
ledger, replay or reporting behaviour before its milestone is approved.
