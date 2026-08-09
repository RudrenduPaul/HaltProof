# HaltProof

[![CI](https://github.com/RudrenduPaul/HaltProof/actions/workflows/ci.yml/badge.svg)](https://github.com/RudrenduPaul/HaltProof/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/haltproof-cli.svg)](https://pypi.org/project/haltproof-cli/)
[![npm](https://img.shields.io/npm/v/haltproof-cli.svg)](https://www.npmjs.com/package/haltproof-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Signed, dry-run-by-default shutdown orchestration for Slurm, Kubernetes,
and IPMI clusters, with a tamper-evident audit trail.**

![HaltProof demo](docs/assets/haltproof-demo.gif)

HaltProof is an emergency-shutdown **orchestration** and **cryptographic
audit-proof** layer for compute clusters. It does not implement a new
low-level shutdown mechanism. It coordinates cluster primitives you already
trust (Slurm, Kubernetes, IPMI/BMC) and produces a signed, tamper-evident
record of exactly what was targeted, what ran, and who authorized it.

Use it for incident response, change-management evidence, and compliance
reporting: for example, generating an auditable "human oversight" trail for
compute infrastructure actions, the kind of evidence required by frameworks
like the EU AI Act's human-oversight provisions.

```bash
pip install haltproof-cli
```

(Full install options, including the npm wrapper, are in
[Install](#install) below.)

## Why

Operators already have the tools to drain a Slurm partition, cordon a
Kubernetes node pool, or power-fence a physical host over IPMI. What's
usually missing is:

1. **One consistent interface** across those tools during an incident,
   instead of three different command sets under pressure.
2. **A dry-run-by-default safety rail**, so a mistyped target group doesn't
   take down the wrong nodes.
3. **A signed, tamper-evident record** of what happened: who ran it, what
   commands were issued, against which nodes, whether each step succeeded,
   and whether the record itself has been altered or has a piece missing.

HaltProof is that layer. It calls out to `scontrol`, `kubectl`, and
`ipmitool` (or `mcp`-invokable equivalents) and wraps every invocation in an
Ed25519-signed, hash-chained attestation.

## Install

**Python (primary distribution):**

```bash
pip install haltproof-cli
```

**Node.js / npm (wrapper around the Python CLI):**

```bash
npm install -g haltproof-cli
```

> [!WARNING]
> The npm package requires the Python `haltproof-cli` package to already be
> installed and on `PATH`. It is a thin `execFileSync` wrapper, not a
> reimplementation. If it can't find the Python CLI, it prints an actionable
> error and exits non-zero rather than silently doing something else.

## Quickstart

> [!IMPORTANT]
> `haltproof halt` is a no-op without `--confirm`. It prints the plan and
> writes a signed dry-run attestation, but nothing destructive runs until
> you pass `--confirm` explicitly.

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

# Verify the entire attestation log's hash chain is intact, not just
# one record: catches a deleted or reordered entry that a single-record
# signature check alone would miss.
haltproof verify --chain --attestation-log ~/.local/share/haltproof/attestations.jsonl
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
run, against which nodes, in what order, and still writes a signed
attestation record of that dry-run plan, so "what would have happened" is
also auditable.

### Config file (optional)

Target groups, the preferred backend, and default paths can be defined in a
`haltproof.toml` file (in the current directory, at
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

## Comparison

HaltProof doesn't compete with Slurm, Kubernetes, or IPMI. It sits on top
of the tools operators already use for exactly this job and adds what none
of them provide on their own: one interface, one safety gate, and a signed
record.

| Capability | HaltProof | `kubectl` (native) | `scontrol` (native) | `ipmitool` (native) |
|---|---|---|---|---|
| Single command across Slurm + Kubernetes + IPMI | Yes | No, Kubernetes only | No, Slurm only | No, IPMI only |
| Consistent dry-run gate before any backend executes | Yes, one `--confirm` flag for all three backends | Partial: `--dry-run=client` validates syntax only, not real cluster mutation | No built-in simulate mode; `state=drain` takes effect immediately | No dry-run concept for power commands |
| Cryptographically signed record of what ran | Yes, Ed25519 | No | No | No |
| Detects a deleted or reordered record in the audit trail | Yes, hash-chained log | No | No | No |
| Structured JSON output for every action | Yes, every command | Partial: `-o json` covers read/get commands, not the `drain`/`cordon` action result | No, plain text only | No, plain text only |
| MCP server for direct AI agent invocation | Yes | No | No | No |

A live GitHub search (2026-08-03) found no existing open-source project
combining unified multi-backend orchestration, a dry-run-by-default gate,
and a cryptographically signed, hash-chained audit trail for cluster
shutdown operations. The closest adjacent projects target a different
layer entirely: behavioral/alignment research on model outputs, not
infrastructure-level shutdown orchestration with an audit trail.

## CLI command reference

Reference below is generated from the CLI's actual `--help` output.

### `haltproof halt TARGET_GROUP`

Drain, isolate, and power-fence `TARGET_GROUP`.

![haltproof keygen, halt, and verify in sequence](docs/demo-halt-verify.gif)

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

### `haltproof verify [ATTESTATION_REF]`

Verify an attestation record's signature, or an entire log's hash chain.

`ATTESTATION_REF` is either a path to a file containing the record, or an
attestation id / sequence number to look up in the attestation log. Pass
`--chain` instead of `ATTESTATION_REF` to verify that a whole
`--attestation-log` is intact: every record's signature holds, sequence
numbers have no gaps, and no record has been deleted or reordered.

```
Options:
  --attestation-log TEXT  Path to the attestation log to search when
                          ATTESTATION_REF is an id or sequence number, or
                          to verify with --chain.
  --trusted-key TEXT      Path to a trusted Ed25519 public key; if given, the
                          record's signing key must match it.
  --chain                 Verify the full hash chain of --attestation-log
                          instead of a single record.
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

![haltproof keygen followed by status --json](docs/demo-keygen-status.gif)

```
Options:
  --output TEXT          Path to write the private key to.
  --force                Overwrite an existing key at the output path.
  --format [human|json]  Output format.
  --json                 Shorthand for --format=json.
```

### `haltproof mcp-server`

Starts the HaltProof MCP server on stdio transport, exposing `halt`,
`verify`, `verify_chain`, `status`, and `keygen` as MCP tools for an AI
agent to invoke programmatically.

## Architecture

HaltProof has three layers:

1. **Transport layer**: the Click-based CLI (`haltproof.cli`) and the MCP
   server (`haltproof.mcp_server`). Both are thin wrappers over the same
   core functions in `haltproof.core`, so a human running the CLI and an
   agent calling the MCP tool get identical behavior, including the
   dry-run-by-default gate on `halt`.

2. **Backend layer**: a `ClusterBackend` abstract interface
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
   `haltproof.backends.detect`, not touching the orchestration or
   attestation layers.

   Backend selection: an explicit `--backend` flag wins, then the config
   file's `backend` key, then auto-detection based on which of
   `kubectl`/`scontrol`/`ipmitool` is found on `PATH`.

3. **Attestation layer** (`haltproof.attestation`): every halt operation
   (dry-run or real) produces one signed, hash-chained record and appends
   it to a local append-only newline-delimited-JSON log.

## Security model

- **Signing.** Attestation records are signed with Ed25519 (`cryptography`
  library). The record's signing public key is embedded in the record
  itself (public keys aren't secret), so `haltproof verify` can check
  internal signature validity on its own. Pass `--trusted-key` to
  additionally require the record be signed by one specific known operator
  key.
- **Tamper evidence, per record.** Signing covers the entire record
  (operator, target nodes, every step's command and status, timestamps,
  the chain link described below) except the signature field itself.
  Changing any field, including hiding a failed step or rewriting who
  authorized the halt, invalidates the signature.
- **Tamper evidence, across the log.** A signature alone only proves one
  record's own content is unaltered. It says nothing about whether a
  record was deleted from the log or reordered. Every record embeds
  `prev_hash`, the content hash of the record immediately before it, so
  `haltproof verify --chain` can confirm sequence numbers have no gaps and
  every link in the chain matches, catching a deleted or reordered record
  even though its neighbors' individual signatures still hold on their
  own.
- **Key handling.** `haltproof keygen` writes the private key with `0600`
  permissions and never prints or logs key material, in CLI output, JSON
  output, or the MCP tool result. Treat the private key like an SSH
  private key: back it up somewhere access-controlled, and rotate it if
  you suspect exposure. Anyone holding it can sign records that verify as
  coming from you.
- **BMC credentials.** The IPMI backend reads the BMC password from the
  `IPMI_PASSWORD` environment variable and passes `ipmitool -E`, so it
  never appears as a command-line argument, in the process list, or in the
  attestation record's logged command.
- **Dry-run by default.** `haltproof halt` requires an explicit `--confirm`
  to execute anything destructive. This is enforced at a single chokepoint
  (`haltproof.backends.runner.run_step`) that every backend routes
  through, not re-implemented per backend.
- **Operator identity.** Recorded from (in order) an explicit
  `--operator-id`, an SSH certificate identity if the environment exposes
  one, or the OS user running the command.

## MCP server (for AI agents)

```bash
haltproof mcp-server
```

Starts an MCP server on stdio exposing `halt`, `verify`, `verify_chain`,
`status`, and `keygen` as tools, built on the official `mcp` Python SDK. An
agent connected over MCP gets the same dry-run-by-default `halt` behavior
and the same JSON-shaped results as the CLI's `--json` mode: the CLI and
the MCP server call the same underlying functions in `haltproof.core`.

## FAQ

**Does HaltProof actually cut power or network access itself?**
No. It calls `scontrol`, `kubectl`, and `ipmitool`, tools you already run
and trust, and wraps each invocation in a dry-run gate and a signed
record. HaltProof adds orchestration and proof, not a new low-level
shutdown mechanism.

**What happens if a node's underlying tool isn't installed?**
The relevant backend reports that step as `failed` with the actual error
(for example, `executable not found`), and the attestation record still
gets written and signed, so the failure itself is part of the auditable
history.

**Can I use HaltProof without signing attestations?**
Yes, `--no-sign` skips signing but still writes the record to the log.
This is meant for local testing, not production incident response, since
an unsigned record can't be verified as authentic.

**Does the attestation log need a central server?**
No. It's a local, append-only NDJSON file by default. `--remote-collector`
optionally POSTs each signed record to a URL you configure, for teams that
want a central copy, but nothing about verification depends on that
server being reachable.

**How is this different from just writing a runbook or Ansible playbook?**
A runbook or playbook can call the same underlying tools, but it doesn't
produce a cryptographically signed, tamper-evident record of what actually
ran on its own. You would need to build that logging and signing layer
yourself. HaltProof ships it as the default behavior.

**What happens if two operators run `halt` at the same time against the
same attestation log?**
Appends are file-locked (`fcntl.flock` on POSIX) so writes don't
interleave, but sequence numbers are assigned by reading the log at the
moment each command starts. Point both operators at backend-specific or
per-incident log files if you need strict per-operation serialization.

**Is this an "AI safety kill switch"?**
No. HaltProof is infrastructure incident-response and compliance-audit
tooling for cluster operators. It has no opinion on AI model behavior and
makes no claims about AI safety or alignment. It orchestrates existing
shutdown primitives and proves what ran, the same way it would for a
non-AI workload.

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
