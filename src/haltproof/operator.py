"""Operator identity resolution for attestation records.

Resolution order: an explicit ``--operator-id``/config value always wins;
otherwise fall back to an SSH certificate identity if one is presented on
the invoking connection; otherwise fall back to the OS user running the
command.
"""

from __future__ import annotations

import getpass
import os


def resolve_operator_id(explicit: str | None = None) -> str:
    """Resolve the operator identity to record in an attestation."""
    if explicit:
        return explicit

    ssh_identity = _ssh_cert_identity()
    if ssh_identity:
        return ssh_identity

    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER", "unknown")


def _ssh_cert_identity() -> str | None:
    """Best-effort extraction of an SSH certificate identity, if present.

    Looks at ``SSH_USER_AUTH`` / ``SSH_CONNECTION``-adjacent environment
    conventions used by some bastion setups to expose the certificate
    principal. Returns ``None`` when no such identity is available rather
    than guessing, since a wrong operator identity in an audit record is
    worse than falling back to the OS user.
    """
    cert_identity = os.environ.get("HALTPROOF_SSH_CERT_IDENTITY")
    if cert_identity:
        return cert_identity
    return None
