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

## FAQ

**Why does an npm package need Python installed?**
This package is a thin wrapper, not a reimplementation. The actual cluster-backend and
Ed25519 signing logic lives in the Python `haltproof-cli` package; this wrapper exists so
npm-based tooling and agent runtimes can shell out to a `haltproof` binary via `npm install`
without hand-rolling a subprocess call themselves.

**Does this wrapper do anything on its own if the Python CLI isn't installed?**
No. It checks for `haltproof` on `PATH` at run time and exits non-zero with an actionable
error message if it isn't found -- it never silently falls back to a different tool or a
partial reimplementation.

**Is this the right package to install if I'm not using npm/Node tooling?**
No -- install the Python package directly with `pip install haltproof-cli` and skip this
wrapper entirely. Use this package only when your existing toolchain is npm-based (a CI step,
an agent runtime, an `npx`-driven workflow) and you want a single `npm install` to pull in the
CLI dependency chain.

**Where do I report a bug or ask a question?**
Open an issue on the [main repository](https://github.com/RudrenduPaul/HaltProof/issues) --
this wrapper has no separate issue tracker.
