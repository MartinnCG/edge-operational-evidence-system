# Security policy

## Supported versions

The project is pre-release. Only the current default branch is supported.

## Reporting

Do not open a public issue containing credentials, personal information,
private-site locations, client data or exploitable operational details. Contact
the repository owner privately through the contact method on the GitHub profile.

## Repository rules

- Never commit API keys, tokens or device credentials.
- Public fixtures must contain synthetic identities and locations.
- Runtime databases and generated evidence directories are ignored by default.
- Dependency additions require an explicit use case and review.
- Findings produced by this reference system must not be represented as
  safety-certified alarms or autonomous control decisions.

This repository currently has no runtime, network or device integration. The
policy will be reviewed before each milestone expands the attack surface.
