# public-surface-sweeper

`public-surface-sweeper` is a small CLI for checking whether a repository is
ready to present as a public project.

It checks for required project files, secret-shaped values, private key blocks,
and public-facing punctuation that is often normalized before publication.

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
```

The command exits with status `1` when error-level findings are present.

## Authorship

Created and maintained by Zain Dana Harper. Claude Code contributed to the
initial implementation.

