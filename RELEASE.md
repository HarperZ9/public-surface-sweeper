# public-surface-sweeper v0.1.1

## Release Type

Patch release for current public package behavior and release-artifact
normalization.

## Verification

- `python -m pytest -q`
- `python -m build`
- `python -m twine check dist/*`
- `python -m public_surface_sweeper examples/clean-repo --proof-packet`
- `git diff --check`

## Artifacts

- `public_surface_sweeper-0.1.1-py3-none-any.whl`
- `public_surface_sweeper-0.1.1.tar.gz`

## Publishing Notes

GitHub Release artifacts are in scope. PyPI publication remains separate and
requires registry credentials.
