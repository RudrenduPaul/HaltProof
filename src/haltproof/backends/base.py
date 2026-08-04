"""Common backend interface that every HaltProof cluster backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class StepStatus(str, Enum):
    """Outcome of a single per-node operation."""

    PLANNED = "planned"
    SUCCESS = "success"
    FAILURE = "failure"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """The result of running (or planning) one operation against one node.

    ``command`` is the literal argv list that was, or would be, executed.
    Keeping it as a list (never a shell string) means attestation records
    show exactly what ran with no shell-quoting ambiguity, and backends never
    need ``shell=True``.
    """

    node: str
    operation: str
    command: list[str]
    status: StepStatus
    detail: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "operation": self.operation,
            "command": self.command,
            "status": self.status.value,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


@dataclass
class NodeStatus:
    """Point-in-time health/reachability summary for a single node."""

    node: str
    reachable: bool
    state: str
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "node": self.node,
            "reachable": self.reachable,
            "state": self.state,
            "detail": self.detail,
        }


class ClusterBackend(ABC):
    """Abstract interface every cluster backend must implement.

    A backend adapts HaltProof's four operations onto one already-trusted
    cluster primitive. Not every primitive supports every operation
    natively (for example Kubernetes has no hard power-fencing mechanism);
    backends that lack a given capability return a ``SKIPPED`` StepResult
    with an explanatory ``detail`` rather than raising, so a mixed-capability
    halt sequence still produces a complete, honest attestation record.
    """

    #: Short machine-readable backend identifier, e.g. "kubernetes".
    name: str = "base"

    @abstractmethod
    def drain(self, nodes: list[str], *, dry_run: bool, reason: str) -> list[StepResult]:
        """Stop new work from being scheduled onto ``nodes``."""

    @abstractmethod
    def isolate_network(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        """Cut ``nodes`` off from the workload network."""

    @abstractmethod
    def power_fence(self, nodes: list[str], *, dry_run: bool) -> list[StepResult]:
        """Hard power off ``nodes``."""

    @abstractmethod
    def status(self, nodes: list[str]) -> list[NodeStatus]:
        """Report current reachability/state for ``nodes``."""
