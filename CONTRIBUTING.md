# Contributing to HaltProof

Thanks for your interest in contributing. HaltProof is an orchestration
and audit-proof layer over cluster primitives operators already trust
(Slurm, Kubernetes, IPMI/BMC), so correctness and honest failure reporting
matter more here than in most projects. Please read this guide before
opening a pull request.

## Getting started

1. Fork the repository and clone your fork.
2. Create a virtual environment and install the package with dev
   dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
3. Run the test suite before making changes, to confirm your environment
   is set up correctly:

   ```bash
   pytest
   ```

## Making changes

- Create a feature branch off `main`: `git checkout -b my-change`.
- Keep pull requests focused on one change. Smaller, self-contained PRs
  are reviewed faster.
- Add or update tests for any behavior change. Backend changes should
  mock `subprocess` calls rather than invoking real `scontrol`/`kubectl`/
  `ipmitool` — tests must not require real cluster infrastructure.
- Run the full test suite locally before opening a PR:

  ```bash
  pytest -v --cov=haltproof --cov-report=term-missing
  ```

## Adding a new backend

HaltProof's backends implement the `ClusterBackend` abstract interface in
`src/haltproof/backends/base.py` (`drain`, `isolate_network`,
`power_fence`, `status`). To add support for a new scheduler or fencing
mechanism:

1. Add a new module under `src/haltproof/backends/`.
2. Implement all four methods. If the underlying primitive doesn't
   support an operation, return a `SKIPPED` `StepResult` with a clear
   explanation rather than raising or silently no-oping.
3. Register the backend in `src/haltproof/backends/detect.py`.
4. Add tests mirroring the existing backend test files, covering command
   construction, dry-run gating, and status parsing.

## Security-sensitive changes

Changes touching attestation signing/verification (`src/haltproof/
attestation.py`), key generation (`src/haltproof/keys.py`), or the
dry-run/`--confirm` gating in `src/haltproof/core.py` warrant extra
scrutiny. If you're proposing a change in this area, explain the
motivation and threat model in your PR description. See `SECURITY.md`
for how to report a vulnerability rather than filing a public issue.

## Code style

- Python 3.10+, type hints on public functions.
- No new destructive operation should ever run without going through the
  existing `dry_run` gate.
- Never log, print, or return private key material from any function.

## Reporting bugs and requesting features

Please open a GitHub issue with:

- What you expected to happen.
- What actually happened (including `--json` output where relevant).
- Your backend (kubernetes/slurm/ipmi) and how it was detected/configured.

## Code of conduct

Be respectful and constructive. This project follows the spirit of the
[Contributor Covenant](https://www.contributor-covenant.org/).
