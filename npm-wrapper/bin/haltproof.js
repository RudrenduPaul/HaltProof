#!/usr/bin/env node
"use strict";

/**
 * Thin wrapper around the haltproof Python CLI.
 *
 * HaltProof's actual implementation is the Python package `haltproof-cli`
 * (installed via `pip install haltproof-cli`). This wrapper exists so
 * Node.js/npm-based tooling and agent runtimes can `npm install -g
 * haltproof-cli` and get a `haltproof` binary on PATH, without needing a
 * separate reimplementation of the CLI, the cluster backends, or the
 * attestation signing logic in JavaScript.
 *
 * If the Python CLI is not found on PATH, this prints a clear, actionable
 * error and exits non-zero. It deliberately does not fall back to
 * installing anything else or attempting any other CLI, since silently
 * substituting a different tool for an infrastructure shutdown command
 * would be far worse than failing loudly.
 */

const { execFileSync } = require("node:child_process");
const { spawnSync } = require("node:child_process");

const PYTHON_CLI_NAME = "haltproof";

function isHaltproofOnPath() {
  const checkCommand = process.platform === "win32" ? "where" : "which";
  const result = spawnSync(checkCommand, [PYTHON_CLI_NAME], {
    stdio: "ignore",
  });
  return result.status === 0;
}

function printMissingCliError() {
  const message = `
haltproof-cli (npm) requires the Python "haltproof" CLI to be installed and on PATH.

It was not found. Install it with:

    pip install haltproof-cli

or, if you use pipx:

    pipx install haltproof-cli

Then re-run this command. This npm package is a thin wrapper around the
Python CLI; it does not reimplement HaltProof and will not fall back to
any other tool.
`;
  process.stderr.write(message.trimStart() + "\n");
}

function main() {
  if (!isHaltproofOnPath()) {
    printMissingCliError();
    process.exit(1);
  }

  const args = process.argv.slice(2);

  try {
    execFileSync(PYTHON_CLI_NAME, args, { stdio: "inherit" });
  } catch (error) {
    if (typeof error.status === "number") {
      process.exit(error.status);
    }
    process.stderr.write(`Failed to run haltproof: ${error.message}\n`);
    process.exit(1);
  }
}

main();
