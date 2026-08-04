"""Pluggable cluster backends for HaltProof.

Each backend implements the :class:`~haltproof.backends.base.ClusterBackend`
interface against a specific already-trusted cluster primitive (Slurm,
Kubernetes, IPMI/BMC). Adding a new scheduler or fencing mechanism means
adding a new backend module, not modifying the orchestration or attestation
layers.
"""

from haltproof.backends.base import ClusterBackend, NodeStatus, StepResult
from haltproof.backends.detect import detect_backend, get_backend

__all__ = [
    "ClusterBackend",
    "NodeStatus",
    "StepResult",
    "detect_backend",
    "get_backend",
]
