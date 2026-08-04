"""IPMI backend: hard power fencing of physical hosts via ``ipmitool``.

IPMI/BMC talks to a host's out-of-band management controller, not the OS or
a scheduler, so it has no concept of scheduler drain state or workload
network policy. Those two operations are reported as SKIPPED with guidance
to pair this backend with the slurm or kubernetes backend for those steps.

The BMC password, when required, is passed via the ``IPMI_PASSWORD``
environment variable and ``ipmitool -E`` rather than as a command-line
argument, so it never appears in the process list, in logs, or in the
attestation record's recorded command list.
"""

from __future__ import annotations

import os
import subprocess

from haltproof.backends.base import ClusterBackend, NodeStatus, StepResult
from haltproof.backends.runner import run_step, skipped


class IpmiBackend(ClusterBackend):
    """Drives ``ipmitool`` for out-of-band hard power control.

    ``nodes`` are BMC hostnames/IP addresses reachable over the management
    network (a node-name-to-BMC-address mapping is expected to be resolved
    by the caller before targets reach this backend).
    """

    name = "ipmi"

    def __init__(self, user: str | None = None, interface: str = "lanplus"):
        self.user = user
        self.interface = interface

    def _base_args(self, bmc_host: str) -> list[str]:
        args = ["ipmitool", "-I", self.interface, "-H", bmc_host]
        if self.user:
            args += ["-U", self.user, "-E"]
        return args

    def _env(self) -> dict | None:
        # -E tells ipmitool to read the BMC password from IPMI_PASSWORD
        # rather than accepting it as a command-line argument.
        if "IPMI_PASSWORD" in os.environ:
            return dict(os.environ)
        return None

    def drain(self, nodes: list[str], *, dry_run: bool, reason: str) -> list[StepResult]:
        return [
            skipped(
                node,
                "drain",
                "IPMI backend manages BMC power state, not scheduler drain state; "
                "use the slurm or kubernetes backend for workload draining.",
            )
            for node in nodes
        ]

    def isolate_network(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        return [
            skipped(
                node,
                "isolate_network",
                "IPMI backend has no workload network-policy primitive; "
                "use the kubernetes backend for network isolation.",
            )
            for node in nodes
        ]

    def power_fence(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        results: list[StepResult] = []
        for node in nodes:
            command = self._base_args(node) + ["chassis", "power", "off"]
            results.append(
                run_step(node, "power_fence", command, dry_run=dry_run, env=self._env())
            )
        return results

    def status(self, nodes: list[str]) -> list[NodeStatus]:
        results: list[NodeStatus] = []
        for node in nodes:
            command = self._base_args(node) + ["chassis", "power", "status"]
            try:
                proc = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=self._env(),
                    check=False,
                )
            except FileNotFoundError:
                results.append(
                    NodeStatus(node=node, reachable=False, state="unknown", detail="ipmitool not found")
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

            output = proc.stdout.strip().lower()
            state = "on" if "is on" in output else ("off" if "is off" in output else "unknown")
            results.append(NodeStatus(node=node, reachable=True, state=state))
        return results
