# HaltProof

[![CI](https://github.com/RudrenduPaul/HaltProof/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/HaltProof/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/haltproof-cli.svg)](https://pypi.org/project/haltproof-cli/)
[![npm](https://img.shields.io/npm/v/haltproof-cli.svg)](https://www.npmjs.com/package/haltproof-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

HaltProof is an emergency-shutdown **orchestration** and **cryptographic
audit-proof** layer for compute clusters. It does not implement a new
low-level shutdown mechanism — it coordinates cluster primitives you
already trust (Slurm, Kubernetes, IPMI/BMC) and produces a signed,
tamper-evident record of exactly what was targeted, what ran, and who
authorized it.

Use it for incident response, change-management evidence, and compliance
reporting — for example, generating an auditable "human oversight" trail
for compute infrastructure actions, the kind of evidence required by
frameworks like the EU AI Act's human-oversight provisions.

## Why

Operators already have the tools to drain a Slurm partition, cordon a
Kubernetes node pool, or power-fence a physical host over IPMI. What's
usually missing is:

1. **One consistent interface** across those tools during an incident,
   instead of three different command sets under pressure.
2. **A dry-run-by-default safety rail**, so a mistyped target group
   doesn't take down the wrong nodes.
3. **A signed record** of what happened — who ran it, what commands were
   issued, against which nodes, and whether each step succeeded — that
   survives being handed to an auditor or incident review board.

HaltProof is that layer. It calls out to `scontrol`, `kubectl`, and
`ipmitool` (or `mcp`-invokable equivalents) and wraps every invocation in
an Ed25519-signed attestation.

## Install

**Python (primary distribution):**

```bash
pip install haltproof-cli
```

**Node.js / npm (wrapper around the Python CLI):**

```bash
npm install -g haltproof-cli
```

The npm package requires the Python `haltproof-cli` package to already be
installed and on `PATH`; it is a thin `execFileSync` wrapper, not a
reimplementation. If it can't find the Python CLI, it prints an
actionable error and exits non-zero rather than silently doing something
else.

## Quickstart

```bash
# Generate a signing key for attestations (do this once).
haltproof keygen --output ~/.config/haltproof/ed25519_key

# See what backend HaltProof auto-detected on this host.
haltproof status

# Dry-run a halt against an explicit node list. Nothing runs yet.
haltproof halt gpu-pod-a --nodes node-1,node-2

# Same halt, actually executed.
haltproof halt gpu-pod-a --nodes node-1,node-2 --confirm

# Verify a past attestation's signature and print its timeline.
haltproof verify 1
```

Every command also supports `--json` for structured, agent-parseable
output:

```bash
haltproof status --json
haltproof halt gpu-pod-a --nodes node-1 --json
```

### Dry-run is the default

`haltproof halt` never executes anything destructive unless you pass
`--confirm`. Without it, HaltProof prints exactly which commands it would
run, against which nodes, in what order — and still writes a signed
attestation record of that dry-run plan, so "what would have happened" is
also auditable.

### Config file (optional)

Target groups, the preferred backend, and default paths can be defined in
a `haltproof.toml` file (in the current directory, at
`~/.config/haltproof/config.toml`, or at a path given by `--config` /
`HALTPROOF_CONFIG`):

```toml
backend = "kubernetes"
operator_id = "ops-team"
attestation_log_path = "/var/log/haltproof/attestations.jsonl"

[groups]
gpu-pod-a = ["node-1", "node-2", "node-3"]

[kubernetes]
namespace = "training"

[ipmi]
user = "admin"
```

Every config value has a corresponding CLI flag, and an explicit flag
always wins over the config file.

## CLI command reference

Reference below is generated from the CLI's actual `--help` output.

### `haltproof halt TARGET_GROUP`

Drain, isolate, and power-fence `TARGET_GROUP`.

```
Options:
  --nodes TEXT             Comma-separated explicit node list, overrides
                           config group lookup.
  --backend TEXT           Backend to use: kubernetes, slurm, or ipmi.
  --confirm                Actually execute the halt. Without this, dry-run
                           only.
  --reason TEXT            Reason recorded for drain operations.
  --operator-id TEXT       Operator identity to record. Defaults to OS user.
  --config TEXT            Path to a haltproof.toml config file.
  --attestation-log TEXT   Path to the attestation log file.
  --attestation-key TEXT   Path to the Ed25519 private key used to sign the
                           attestation.
  --no-sign                Skip signing (not recommended); still logs the
                           record unsigned.
  --remote-collector TEXT  Optional URL to POST the signed attestation to.
  --format [human|json]    Output format.
  --json                   Shorthand for --format=json.
```

### `haltproof verify ATTESTATION_REF`

Verify the signature of an attestation record and print its timeline.
`ATTESTATION_REF` is either a path to a file containing the record, or an
attestation id / sequence number to look up in the attestation log.

```
Options:
  --attestation-log TEXT  Path to the attestation log to search when
                          ATTESTATION_REF is an id or sequence number.
  --trusted-key TEXT      Path to a trusted Ed25519 public key; if given, the
                          record's signing key must match it.
  --format [human|json]   Output format.
  --json                  Shorthand for --format=json.
```

### `haltproof status`

Show backend auto-detection results and optional target-group health.

```
Options:
  --backend TEXT         Backend to check status for; defaults to auto-
                         detected/configured backend.
  --nodes TEXT           Comma-separated node list to report health for.
  --group TEXT           Named target group (from config) to report health
                         for.
  --config TEXT          Path to a haltproof.toml config file.
  --format [human|json]  Output format.
  --json                 Shorthand for --format=json.
```

### `haltproof keygen`

Generate an Ed25519 keypair for attestation signing. The private key is
written with `0600` permissions and is never printed or logged.

```
Options:
  --output TEXT          Path to write the private key to.
  --force                Overwrite an existing key at the output path.
  --format [human|json]  Output format.
  --json                 Shorthand for --format=json.
```

### `haltproof mcp-server`

Starts the HaltProof MCP server on stdio transport, exposing `halt`,
`verify`, `status`, and `keygen` as MCP tools for an AI agent to invoke
programmatically.

## Architecture

HaltProof has three layers:

1. **Transport layer** — the Click-based CLI (`haltproof.cli`) and the
   MCP server (`haltproof.mcp_server`). Both are thin wrappers over the
   same core functions in `haltproof.core`, so a human running the CLI
   and an agent calling the MCP tool get identical behavior — including
   the dry-run-by-default gate on `halt`.

2. **Backend layer** — a `ClusterBackend` abstract interface
   (`haltproof.backends.base`) with four operations:

   ```
   ClusterBackend
   ├── drain(nodes, dry_run, reason)         -> stop new work being scheduled
   ├── isolate_network(nodes, dry_run)       -> cut nodes off from the workload network
   ├── power_fence(nodes, dry_run)           -> hard power off
   └── status(nodes)                         -> current reachability/state
   ```

   Three backends implement it today:

   | Backend | drain | isolate_network | power_fence | Underlying tool |
   |---|---|---|---|---|
   | `kubernetes` | cordon + drain | deny-all NetworkPolicy | not supported (use `ipmi`) | `kubectl` |
   | `slurm` | `scontrol update state=drain` | `state=power_down` (SuspendProgram hook) | not supported (use `ipmi`) | `scontrol` |
   | `ipmi` | not supported (use `slurm`/`kubernetes`) | not supported | `ipmitool chassis power off` | `ipmitool` |

   A backend that doesn't support a given operation returns a `SKIPPED`
   result with an explanation instead of raising, so a halt sequence
   against a mixed environment still produces one complete, honest
   attestation record. Adding support for a new scheduler or fencing tool
   means adding one new backend module and registering it in
   `haltproof.backends.detect` — not touching the orchestration or
   attestation layers.

   Backend selection: an explicit `--backend` flag wins, then the config
   file's `backend` key, then auto-detection based on which of
   `kubectl`/`scontrol`/`ipmitool` is found on `PATH`.

3. **Attestation layer** (`haltproof.attestation`) — every halt operation
   (dry-run or real) produces one signed record and appends it to a local
   append-only newline-delimited-JSON log.

## Security model

- **Signing.** Attestation records are signed with Ed25519
  (`cryptography` library). The record's signing public key is embedded
  in the record itself (public keys aren't secret), so `haltproof verify`
  can check internal signature validity on its own. Pass `--trusted-key`
  to additionally require the record be signed by one specific known
  operator key.
- **Tamper evidence.** Signing covers the entire record (operator,
  target nodes, every step's command and status, timestamps) except the
  signature field itself. Changing any field — including hiding a
  failed step or rewriting who authorized the halt — invalidates the
  signature.
- **Key handling.** `haltproof keygen` writes the private key with
  `0600` permissions and never prints or logs key material, in CLI
  output, JSON output, or the MCP tool result. Treat the private key like
  an SSH private key: back it up somewhere access-controlled, and rotate
  it if you suspect exposure. Anyone holding it can sign records that
  verify as coming from you.
- **BMC credentials.** The IPMI backend reads the BMC password from the
  `IPMI_PASSWORD` environment variable and passes `ipmitool -E`, so it
  never appears as a command-line argument, in the process list, or in
  the attestation record's logged command.
- **Dry-run by default.** `haltproof halt` requires an explicit
  `--confirm` to execute anything destructive. This is enforced at a
  single chokepoint (`haltproof.backends.runner.run_step`) that every
  backend routes through, not re-implemented per backend.
- **Operator identity.** Recorded from (in order) an explicit
  `--operator-id`, an SSH certificate identity if the environment exposes
  one, or the OS user running the command.

<!-- TODO: benchmark comparison table -->

## MCP server (for AI agents)

```bash
haltproof mcp-server
```

Starts an MCP server on stdio exposing `halt`, `verify`, `status`, and
`keygen` as tools, built on the official `mcp` Python SDK. An agent
connected over MCP gets the same dry-run-by-default `halt` behavior and
the same JSON-shaped results as the CLI's `--json` mode — the CLI and the
MCP server call the same underlying functions in `haltproof.core`.

## Development

```bash
git clone https://github.com/RudrenduPaul/HaltProof.git
cd HaltProof
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -v --cov=haltproof --cov-report=term-missing
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add a new backend and
[SECURITY.md](SECURITY.md) for how to report a vulnerability.

## License

[MIT](LICENSE) © Rudrendu Paul
