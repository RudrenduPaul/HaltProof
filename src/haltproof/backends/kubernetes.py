"""Kubernetes backend: cordon/drain nodes and apply a deny-all NetworkPolicy.

Kubernetes has no built-in hard power-fencing primitive (it manages
workloads, not physical power), so ``power_fence`` on this backend is
reported as SKIPPED with guidance to pair it with the IPMI backend for
physical hosts that need a hard power cut.
"""

from __future__ import annotations

import json
import subprocess

from haltproof.backends.base import ClusterBackend, NodeStatus, StepResult, StepStatus
from haltproof.backends.runner import run_step, skipped

_DENY_ALL_POLICY_TEMPLATE = """\
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: haltproof-deny-all-{group}
  namespace: {namespace}
spec:
  podSelector: {{}}
  policyTypes:
    - Ingress
    - Egress
"""


class KubernetesBackend(ClusterBackend):
    """Drives ``kubectl`` to cordon, drain, and network-isolate nodes."""

    name = "kubernetes"

    def __init__(self, namespace: str = "default", group: str = "haltproof"):
        self.namespace = namespace
        self.group = group

    def drain(self, nodes: list[str], *, dry_run: bool, reason: str) -> list[StepResult]:
        results: list[StepResult] = []
        for node in nodes:
            cordon_cmd = ["kubectl", "cordon", node]
            results.append(run_step(node, "cordon", cordon_cmd, dry_run=dry_run))

            drain_cmd = [
                "kubectl",
                "drain",
                node,
                "--ignore-daemonsets",
                "--delete-emptydir-data",
                "--force",
                "--grace-period=30",
            ]
            results.append(run_step(node, "drain", drain_cmd, dry_run=dry_run))
        return results

    def isolate_network(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        manifest = _DENY_ALL_POLICY_TEMPLATE.format(
            group=self.group, namespace=self.namespace
        )
        command = ["kubectl", "apply", "-n", self.namespace, "-f", "-"]
        results: list[StepResult] = []

        if dry_run:
            for node in nodes:
                results.append(
                    StepResult(
                        node=node,
                        operation="isolate_network",
                        command=command + ["<manifest below>"],
                        status=StepStatus.PLANNED,
                        detail=manifest.strip(),
                    )
                )
            return results

        try:
            proc = subprocess.run(
                command,
                input=manifest,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            status = StepStatus.SUCCESS if proc.returncode == 0 else StepStatus.FAILURE
            detail = (proc.stdout if proc.returncode == 0 else proc.stderr).strip()[:500]
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            status = StepStatus.FAILURE
            detail = str(exc)

        for node in nodes:
            results.append(
                StepResult(
                    node=node,
                    operation="isolate_network",
                    command=command,
                    status=status,
                    detail=detail,
                )
            )
        return results

    def power_fence(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        return [
            skipped(
                node,
                "power_fence",
                "Kubernetes backend has no physical power-fencing primitive; "
                "use the ipmi backend for hard power fencing of the underlying hosts.",
            )
            for node in nodes
        ]

    def status(self, nodes: list[str]) -> list[NodeStatus]:
        results: list[NodeStatus] = []
        for node in nodes:
            try:
                proc = subprocess.run(
                    ["kubectl", "get", "node", node, "-o", "json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
            except FileNotFoundError:
                results.append(
                    NodeStatus(node=node, reachable=False, state="unknown", detail="kubectl not found")
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

            try:
                data = json.loads(proc.stdout)
                conditions = data.get("status", {}).get("conditions", [])
                ready = next((c for c in conditions if c.get("type") == "Ready"), None)
                is_ready = bool(ready and ready.get("status") == "True")
                unschedulable = data.get("spec", {}).get("unschedulable", False)
                state = "cordoned" if unschedulable else ("ready" if is_ready else "not-ready")
                results.append(NodeStatus(node=node, reachable=True, state=state))
            except (json.JSONDecodeError, KeyError) as exc:
                results.append(
                    NodeStatus(node=node, reachable=False, state="unknown", detail=str(exc))
                )
        return results
