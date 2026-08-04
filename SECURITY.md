# Security Policy

HaltProof orchestrates shutdown/isolation actions against real
infrastructure and produces signed audit records of those actions. We
take security reports seriously and appreciate responsible disclosure.

## Supported versions

Security fixes are made against the latest published release on PyPI
(`haltproof-cli`) and npm (`haltproof-cli`), and against the `main`
branch of this repository. There is no long-term-support branch at this
stage of the project.

## Reporting a vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report it privately through one of these channels:

- GitHub: use the "Report a vulnerability" option under this
  repository's Security tab (private Security Advisory).
- Email: open an issue asking to be pointed to a current contact email
  if the Security Advisory option is unavailable to you.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce, including which backend (Slurm/Kubernetes/IPMI)
  and CLI/MCP invocation was involved, if applicable.
- Any relevant logs or attestation records (redact operator identity,
  hostnames, or credentials from anything you share).

## Scope

In scope:

- The `haltproof` Python CLI and its backends (`src/haltproof/`).
- The Ed25519 attestation signing and verification logic
  (`src/haltproof/attestation.py`, `src/haltproof/keys.py`).
- The MCP server (`src/haltproof/mcp_server.py`).
- The Node.js npm wrapper (`npm-wrapper/`).

Out of scope:

- Vulnerabilities in the underlying tools HaltProof calls out to
  (`scontrol`, `kubectl`, `ipmitool`) — please report those to the
  respective upstream projects.
- Vulnerabilities requiring an attacker to already have the Ed25519
  private key used for attestation signing; key custody is the
  operator's responsibility (see the README's security model section).

## Response expectations

- We aim to acknowledge new reports within 5 business days.
- We aim to provide an initial assessment (confirmed/not confirmed,
  rough severity) within 10 business days.
- Fix timelines depend on severity; critical issues (for example, a
  signature-forgery path or a way to bypass the `--confirm` dry-run
  gate) are prioritized ahead of routine maintenance.

## Disclosure

We will credit reporters (unless you prefer to remain anonymous) in the
release notes once a fix ships, and we ask that you give us a reasonable
window to ship a fix before public disclosure.
