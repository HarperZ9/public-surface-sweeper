# Changelog

## Unreleased

- Expands the scanner into a two-audience forward-facing delivery contract:
  public clarity/status/funding surfaces and developer handoff/usage/CI
  surfaces.
- Adds normalized rules for `public-changelog`, `public-funding`,
  `developer-agent-instructions`, `developer-usage-doc`, and
  `developer-ci-workflow`.
- Splits the scanner internals into focused modules for models, file IO,
  README delivery, text hygiene, summaries, proof packets, and delivery
  contract checks.
- Updates the clean fixture so command examples exercise the full contract.
- Makes workspace mode traverse local-only wrapper repos and use fast
  delivery-surface scans, so large dependency/source trees do not dominate
  portfolio rollout checks.
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
- Deduplicates multiple local checkouts of the same GitHub remote so portfolio
  delivery counts track repositories rather than mirrors.

## v0.1.1 - 2026-06-14

- Adds proof-surface packet output for release-readiness handoffs.
- Adds a public-safe clean fixture for smoke testing.
- Adds release-artifact packaging workflow and release checklist.
- Keeps the package dependency-light and deterministic.

## v0.1.0 - 2026-06-12

- Initial public release of repository public-surface hygiene checks.
