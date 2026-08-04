"""Backend auto-detection.

Detection order when no explicit choice is made: Kubernetes, then Slurm,
then IPMI, based on whether each primitive's CLI tool is on PATH. An
explicit ``--backend`` flag or a ``backend`` key in the config file always
wins over auto-detection.
"""

from __future__ import annotations

import shutil

from haltproof.backends.base import ClusterBackend
from haltproof.backends.ipmi import IpmiBackend
from haltproof.backends.kubernetes import KubernetesBackend
from haltproof.backends.slurm import SlurmBackend

_BACKEND_TOOLS = {
    "kubernetes": "kubectl",
    "slurm": "scontrol",
    "ipmi": "ipmitool",
}

_BACKEND_CLASSES = {
    "kubernetes": KubernetesBackend,
    "slurm": SlurmBackend,
    "ipmi": IpmiBackend,
}

# Order matters: Kubernetes and Slurm are checked before IPMI, since
# clusters running a scheduler almost always also expose ipmitool on
# management hosts, but the scheduler is the more specific and more useful
# default target for drain/isolate operations.
_DETECTION_ORDER = ["kubernetes", "slurm", "ipmi"]


def detect_available_backends() -> dict[str, bool]:
    """Return which backend CLI tools are present on PATH."""
    return {name: shutil.which(tool) is not None for name, tool in _BACKEND_TOOLS.items()}


def detect_backend() -> str | None:
    """Return the name of the first available backend in detection order."""
    available = detect_available_backends()
    for name in _DETECTION_ORDER:
        if available.get(name):
            return name
    return None


def get_backend(name: str, **kwargs) -> ClusterBackend:
    """Instantiate the backend class for ``name``.

    Raises ``ValueError`` for an unknown backend name, so callers get a
    clear error instead of a KeyError deep in dispatch logic.
    """
    try:
        backend_cls = _BACKEND_CLASSES[name]
    except KeyError as exc:
        valid = ", ".join(sorted(_BACKEND_CLASSES))
        raise ValueError(f"unknown backend {name!r}; valid backends: {valid}") from exc
    return backend_cls(**kwargs)


def known_backend_names() -> list[str]:
    return list(_BACKEND_CLASSES)
