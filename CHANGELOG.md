# Changelog

## Unreleased

- Adds value-focused generic credential-assignment detection for token, API key,
  client secret, and password fields.
- Keeps placeholders and secret-shaped labels out of findings so release gates
  stay actionable.
- Adds warning-level README delivery checks for public value, developer
  workflow, runnable commands, and substantive visual assets.
- Includes README delivery evidence in proof-surface packet claims.
- Recognizes centered HTML `<img src="...">` README hero images as
  substantive visual assets when the referenced file exists.
- Adds workspace delivery matrix mode for scanning every local GitHub-facing
  repository under a workspace root with separate public, developer, and
  boundary verdicts.

## v0.1.1 - 2026-06-14

- Adds proof-surface packet output for release-readiness handoffs.
- Adds a public-safe clean fixture for smoke testing.
- Adds release-artifact packaging workflow and release checklist.
- Keeps the package dependency-light and deterministic.

## v0.1.0 - 2026-06-12

- Initial public release of repository public-surface hygiene checks.
