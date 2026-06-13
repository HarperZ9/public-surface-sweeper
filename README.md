# public-surface-sweeper

`public-surface-sweeper` is a small CLI for checking whether a repository is
ready to present as a public project.

It checks for required project files, secret-shaped values, private key blocks,
and public-facing punctuation that is often normalized before publication.

It is intended as a release-hygiene gate, not a full security scanner or
certification tool.

## Install

```bash
python -m pip install public-surface-sweeper
```

For local development:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

## Usage

```bash
public-surface-sweeper .
public-surface-sweeper . --json
public-surface-sweeper . --summary
public-surface-sweeper . --summary --json
public-surface-sweeper . --fail-on warning
```

The command exits with status `1` when error-level findings are present.

Use `--fail-on warning` to fail on warnings and errors, or `--fail-on none` to
print findings without failing the process.

Run the bundled clean fixture:

```bash
public-surface-sweeper examples/clean-repo
```

Expected output:

```text
No findings.
```

## What it checks

Required project files:

- `README.md`
- `LICENSE`
- `AUTHORS.md`
- `CONTRIBUTING.md`

Text hygiene:

- em dash characters in public-facing text

Secret-shaped values:

- private key block markers
- GitHub token shaped values
- OpenAI key shaped values
- AWS access key shaped values
- Slack token shaped values

The scanner skips common cache, build, virtualenv, and dependency directories.
It also skips binary files and text files larger than 1 MB.

## Example text output

```text
ERROR LICENSE required-file: missing required file: LICENSE
ERROR README.md:12 em-dash: replace em dash with plain punctuation
```

## Example JSON output

```json
[
  {
    "path": "LICENSE",
    "line": 0,
    "rule": "required-file",
    "severity": "error",
    "message": "missing required file: LICENSE"
  }
]
```

## Example summary output

```text
score: 75
status: blocked
total_findings: 1
errors: 1
warnings: 0
action_items:
- LICENSE: missing required file: LICENSE
```

Summary mode is the fastest handoff format for release reviews. It gives a
bounded readiness score, a status, finding counts, and the first actionable
items to fix before publishing or showing the repository to a reviewer.

## What it does not do

- It does not perform exploit testing.
- It does not audit dependencies for vulnerabilities.
- It does not validate whether a credential is real.
- It does not certify that a repository is safe, compliant, or trustworthy.
- It does not replace a security review.

## Release-readiness use

`public-surface-sweeper` is the first point in a proof-surface pipeline:

```text
repo public surface -> hygiene findings -> proof index -> release-readiness report
```

Its job is to catch basic public-surface defects before a repository asks users,
clients, employers, or reviewers to trust it.

## Authorship

Created and maintained by Zain Dana Harper. Claude Code contributed to the
initial implementation.
