# Changelog

All notable changes to HaltProof are documented in this file. This covers
both distributions -- the PyPI package (`haltproof-cli`, Python,
`src/haltproof/`) and the npm package (`haltproof-cli`, Node.js,
`npm-wrapper/`, a thin wrapper that shells out to the Python CLI) -- since
they implement the same command surface; entries note which distribution
they apply to.

## [0.1.2] - PyPI only -- fix stale `--version` output, decouple version source

**Known issue on the currently published `0.1.1` PyPI release**: `haltproof
--version` prints `haltproof, version 0.1.0` no matter which version is
actually installed. `pip show haltproof-cli` correctly reports `0.1.1`,
but the CLI's own `--version` flag (`click.version_option` in
`src/haltproof/cli.py`) reads a hardcoded `__version__ = "0.1.0"` string
from `src/haltproof/__init__.py` that was never bumped when `0.1.1` was
built and published, so the two silently diverged. Separately, the
repository's committed `pyproject.toml` still read `version = "0.1.0"`
even though `0.1.1` was already live on PyPI -- the bump used to publish
`0.1.1` was never committed back, so the two version fields
(`pyproject.toml` and `__init__.py`) were each stale in a different way.
Both are fixed in this version:

- **`pyproject.toml`'s `[project] version` field is now `dynamic`, sourced
  from `src/haltproof/__init__.py`** via `[tool.hatch.version] path =
  "src/haltproof/__init__.py"`, instead of being a second, independently
  hand-maintained version string. `__version__` in
  `src/haltproof/__init__.py` is now the single source of truth for both
  the package's build metadata (what `pip show` reports) and its own
  `--version` output, so the two cannot drift apart again -- bumping the
  version means editing exactly one file.
- Verified via a clean-room rebuild: `python -m build --wheel` from the
  fixed `pyproject.toml`, installed with `pip install` into a fresh,
  disposable venv. `haltproof --version` and `pip show haltproof-cli` now
  agree (`0.1.2`), and the full documented quickstart (`keygen`, `status`,
  `halt` dry-run with `--json`, `verify`, `verify --chain`) still produces
  correct stdout output and exit code `0`.
- All 76 existing tests pass unchanged (`pytest -v --cov=haltproof`, 90%
  coverage, no regressions).
- The npm package (`haltproof-cli`, `npm-wrapper/`) is unaffected and not
  republished as part of this fix. It is a thin `execFileSync`
  pass-through (`npm-wrapper/bin/haltproof.js`) with no version string of
  its own -- it already prints whatever the installed Python CLI's
  `--version` reports, so it will show the corrected version automatically
  once a user's Python `haltproof-cli` is upgraded.

## [0.1.1] - Documentation

Added an FAQ section to the npm wrapper's README (`npm-wrapper/README.md`)
covering why the npm package needs Python installed, what it does if the
Python CLI isn't found, and where to report issues. PyPI long-description
and npm package metadata refreshed to match.

## [0.1.0] - Initial release

First public release of HaltProof: the `haltproof` CLI (`halt`, `verify`,
`status`, `keygen`, `mcp-server`), the `ClusterBackend` interface with
`kubernetes`, `slurm`, and `ipmi` backends, Ed25519-signed and
hash-chained attestation logging, an MCP server exposing the same
operations to AI agents, and the npm wrapper package.
