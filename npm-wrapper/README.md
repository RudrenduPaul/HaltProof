# haltproof-cli (npm)

This is a thin Node.js wrapper around the [HaltProof](https://github.com/RudrenduPaul/HaltProof)
Python CLI. It exists so npm-based tooling and agent runtimes can install a
`haltproof` binary via npm without a separate JavaScript reimplementation
of the CLI, the cluster backends, or the attestation signing logic.

## Requirements

This package requires the Python `haltproof-cli` package to be installed
and on `PATH`:

```bash
pip install haltproof-cli
```

If the `haltproof` executable is not found on `PATH`, this wrapper prints
an actionable error and exits non-zero. It never falls back to installing
or running a different tool.

## Install

```bash
npm install -g haltproof-cli
```

## Usage

All arguments are passed straight through to the Python CLI:

```bash
haltproof status --json
haltproof halt gpu-pod-a --nodes node-1,node-2
haltproof keygen --output ~/.config/haltproof/ed25519_key
```

See the [main README](https://github.com/RudrenduPaul/HaltProof#readme) for
full command documentation.
