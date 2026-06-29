# Usage Guide

`public-surface-sweeper` is a pre-release repo-hygiene CLI. It checks for
required project files, em dash characters in public-facing text,
secret-shaped values, and README delivery quality. It is a hygiene gate, not a
vulnerability scanner.

This guide covers the real CLI and the importable Python API. Every flag,
command, and function shown here exists in the current source.

## Install

```bash
python -m pip install public-surface-sweeper
```

For local development from a clone:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Requires Python 3.10+.

## Command line

The console script is `public-surface-sweeper`. You can also invoke it as a
module with `python -m public_surface_sweeper`.

```
public-surface-sweeper [ROOT] [--json] [--summary] [--proof-packet] [--fail-on {none,warning,error}]
```

- `ROOT` - repository root to scan. Optional; defaults to `.`.
- `--json` - print findings as a JSON array.
- `--summary` - print a release-readiness summary instead of individual findings.
- `--summary --json` - print the summary as a JSON object.
- `--proof-packet` - print a proof-surface interop packet as JSON.
- `--fail-on {none,warning,error}` - minimum severity that returns a failing
  exit code. Default is `error`.

The process exits `1` when findings at or above the `--fail-on` threshold are
present, otherwise `0`. Required-file, punctuation, and secret-shaped findings
are errors. README delivery findings are warnings.

## Python API

```python
from pathlib import Path
from public_surface_sweeper.sweeper import (
    scan,
    summarize_findings,
    format_text,
    format_summary,
    proof_surface_packet,
)

findings = scan(Path("examples/clean-repo"))   # list[Finding]
summary = summarize_findings(findings)          # SweepSummary
print(format_text(findings))                    # human-readable text
print(format_summary(summary))                  # human-readable summary
packet = proof_surface_packet(Path("."), findings)  # dict (proof-surface shape)
```

`scan(root)` returns a sorted `list[Finding]`. Each `Finding` has the fields
`path`, `line`, `rule`, `severity`, and `message`. `summarize_findings`
returns a `SweepSummary` with `score`, `status`, `total_findings`, `errors`,
`warnings`, and `action_items`.

## Worked examples

The expected output below was produced by running the commands against the
bundled `examples/clean-repo` fixture and a small repository that is missing
two required files and contains an em dash and a GitHub-token-shaped value.

### 1. Scan a clean repository

```bash
public-surface-sweeper examples/clean-repo
```

Expected output:

```text
No findings.
```

Exit code: `0`.

### 2. Scan a repository with problems (text)

Given a repo missing `AUTHORS.md` and `CONTRIBUTING.md`, with an em dash on
line 2 of `README.md` and a GitHub-token-shaped value on line 3:

```bash
public-surface-sweeper ./my-repo
```

Expected output:

```text
ERROR AUTHORS.md required-file: missing required file: AUTHORS.md
ERROR CONTRIBUTING.md required-file: missing required file: CONTRIBUTING.md
ERROR README.md:2 em-dash: replace em dash with plain punctuation
ERROR README.md:3 github-token: GitHub token shaped value
```

Exit code: `1`.

### 3. Release-readiness summary

```bash
public-surface-sweeper ./my-repo --summary
```

Expected output:

```text
score: 0
status: blocked
total_findings: 4
errors: 4
warnings: 0
action_items:
- AUTHORS.md: missing required file: AUTHORS.md
- CONTRIBUTING.md: missing required file: CONTRIBUTING.md
- README.md:2: replace em dash with plain punctuation
- README.md:3: GitHub token shaped value
```

The same data as a JSON object:

```bash
public-surface-sweeper examples/clean-repo --summary --json
```

Expected output:

```json
{
  "score": 100,
  "status": "ready",
  "total_findings": 0,
  "errors": 0,
  "warnings": 0,
  "action_items": []
}
```

### 4. Proof-surface packet for a pipeline

```bash
public-surface-sweeper ./my-repo --proof-packet > public-surface.packet.json
```

Expected output (for the problem repo above):

```json
{
  "proof_surface_version": "0.1",
  "packet_id": "public-surface-sweeper-my-repo",
  "surface": "my-repo public release surface",
  "status": "blocked",
  "claims": [
    {
      "claim": "Required public release files are visible.",
      "evidence": "required-file findings=2"
    },
    {
      "claim": "Secret-shaped values are surfaced before publication.",
      "evidence": "secret-shaped findings=1"
    },
    {
      "claim": "Public text hygiene is checkable.",
      "evidence": "em-dash findings=1"
    },
    {
      "claim": "Public and developer delivery are inspectable.",
      "evidence": "readme delivery findings=0"
    }
  ],
  "checks": [
    {
      "tool": "public-surface-sweeper",
      "status": "fail",
      "summary": "score=0, findings=4"
    }
  ],
  "action_items": [
    "AUTHORS.md: missing required file: AUTHORS.md",
    "CONTRIBUTING.md: missing required file: CONTRIBUTING.md",
    "README.md:2: replace em dash with plain punctuation",
    "README.md:3: GitHub token shaped value"
  ]
}
```

The generated packet is self-validated before printing. If validation fails,
the command writes an error to stderr and exits `1`.

## Exit codes

- `0` - no findings at or above the `--fail-on` threshold.
- `1` - findings at or above the threshold, or a proof-packet that failed
  internal validation.

Use `--fail-on none` to print findings without failing the process (useful in
report-only mode), or `--fail-on warning` to also fail on warnings.
