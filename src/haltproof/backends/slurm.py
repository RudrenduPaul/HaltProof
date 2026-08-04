"""Slurm backend: drain and suspend nodes via ``scontrol``.

Slurm is a workload scheduler, not a network fabric or a BMC, so it has no
native network-isolation or physical power-fencing primitive. Those two
operations are reported as SKIPPED with guidance to pair this backend with
the kubernetes or ipmi backend when isolation or hard power-off is required.
"""

from __future__ import annotations

import subprocess

from haltproof.backends.base import ClusterBackend, NodeStatus, StepResult
from haltproof.backends.runner import run_step, skipped


class SlurmBackend(ClusterBackend):
    """Drives ``scontrol`` to drain nodes and trigger the SuspendProgram hook."""

    name = "slurm"

    def drain(self, nodes: list[str], *, dry_run: bool, reason: str) -> list[StepResult]:
        results: list[StepResult] = []
        for node in nodes:
            command = [
                "scontrol",
                "update",
                f"nodename={node}",
                "state=drain",
                f"reason={reason}",
            ]
            results.append(run_step(node, "drain", command, dry_run=dry_run))
        return results

    def isolate_network(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        # Slurm's own mechanism for taking a node fully out of service beyond
        # scheduling is its power-save / SuspendProgram hook. We surface that
        # as the "isolate" step for this backend, since Slurm has no separate
        # network-policy concept of its own.
        results: list[StepResult] = []
        for node in nodes:
            command = ["scontrol", "update", f"nodename={node}", "state=power_down"]
            results.append(run_step(node, "suspend", command, dry_run=dry_run))
        return results

    def power_fence(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        return [
            skipped(
                node,
                "power_fence",
                "Slurm backend has no physical power-fencing primitive; "
                "use the ipmi backend for hard power fencing of the underlying hosts.",
            )
            for node in nodes
        ]

    def status(self, nodes: list[str]) -> list[NodeStatus]:
        results: list[NodeStatus] = []
        for node in nodes:
            try:
                proc = subprocess.run(
                    ["scontrol", "show", "node", node],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except FileNotFoundError:
                results.append(
                    NodeStatus(node=node, reachable=False, state="unknown", detail="scontrol not found")
                )
                continue

            if proc.returncode != 0:
                results.append(
                    NodeStatus(
                        node=node,
                        reachable=False,
                        state="unknown",
                        detail=proc.stderr.strip()[:300],
                    )
                )
                continue

            output = proc.stdout
            state = "unknown"
            for token in output.split():
                if token.startswith("State="):
                    state = token.split("=", 1)[1].lower()
                    break
            results.append(NodeStatus(node=node, reachable=True, state=state))
        return results
