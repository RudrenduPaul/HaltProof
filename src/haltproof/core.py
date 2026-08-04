"""Core operation logic shared by the CLI and the MCP server.

Keeping this logic in one place means the CLI and the MCP server are two
thin transports over the same behavior, rather than two separately
maintained implementations that could drift apart.
"""

from __future__ import annotations

import json as json_module
import urllib.error
import urllib.request
from pathlib import Path

from haltproof.attestation import (
    AttestationError,
    AttestationLog,
    SignatureVerificationError,
    build_record,
    load_record_from_file,
    sign_record,
    verify_record,
)
from haltproof.backends.base import StepResult
from haltproof.backends.detect import (
    detect_available_backends,
    detect_backend,
    get_backend,
    known_backend_names,
)
from haltproof.config import load_config
from haltproof.keys import generate_keypair, load_private_key, load_public_key
from haltproof.operator import resolve_operator_id

DEFAULT_ATTESTATION_LOG = Path.home() / ".local" / "share" / "haltproof" / "attestations.jsonl"
DEFAULT_KEY_PATH = Path.home() / ".config" / "haltproof" / "ed25519_key"


class HaltProofError(Exception):
    """Domain error with a message safe to surface to a CLI user or an agent."""


def _build_backend(backend_name: str, config):
    kwargs = {}
    if backend_name == "kubernetes":
        kwargs["namespace"] = config.namespace
    elif backend_name == "ipmi":
        if config.ipmi_user:
            kwargs["user"] = config.ipmi_user
    return get_backend(backend_name, **kwargs)


def resolve_backend_name(explicit: str | None, config) -> str:
    name = explicit or config.backend or detect_backend()
    if not name:
        available = ", ".join(known_backend_names())
        raise HaltProofError(
            "no backend could be auto-detected (none of scontrol/kubectl/ipmitool "
            f"found on PATH); pass an explicit backend. Valid backends: {available}"
        )
    if name not in known_backend_names():
        available = ", ".join(known_backend_names())
        raise HaltProofError(f"unknown backend {name!r}; valid backends: {available}")
    return name


def _post_to_collector(url: str, payload: dict) -> str:
    data = json_module.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return f"{response.status}"
    except urllib.error.URLError as exc:
        return f"error: {exc}"


def run_halt(
    *,
    target_group: str,
    nodes: list[str] | None = None,
    backend_name: str | None = None,
    confirm: bool = False,
    reason: str = "haltproof halt requested",
    operator_id: str | None = None,
    config_path: str | None = None,
    attestation_log_path: str | None = None,
    attestation_key_path: str | None = None,
    no_sign: bool = False,
    remote_collector_url: str | None = None,
) -> dict:
    """Run a halt sequence (dry-run unless ``confirm`` is True) and record an attestation."""
    config = load_config(config_path)

    node_list = nodes or config.resolve_group(target_group)
    if not node_list:
        raise HaltProofError(
            f"no nodes resolved for target group {target_group!r}; pass an explicit node "
            "list or define it under [groups] in a haltproof config file."
        )

    resolved_backend_name = resolve_backend_name(backend_name, config)
    backend = _build_backend(resolved_backend_name, config)

    dry_run = not confirm
    all_steps: list[StepResult] = []
    all_steps += backend.drain(node_list, dry_run=dry_run, reason=reason)
    all_steps += backend.isolate_network(node_list, dry_run=dry_run)
    all_steps += backend.power_fence(node_list, dry_run=dry_run)

    operator = resolve_operator_id(operator_id or config.operator_id)
    log_path = Path(attestation_log_path or config.attestation_log_path or DEFAULT_ATTESTATION_LOG)
    attestation_log = AttestationLog(log_path)
    next_seq, prev_hash = attestation_log.chain_state()

    record = build_record(
        seq=next_seq,
        operator=operator,
        action="halt",
        target_group=target_group,
        backend=resolved_backend_name,
        nodes=node_list,
        dry_run=dry_run,
        confirmed=confirm,
        steps=all_steps,
        prev_hash=prev_hash,
    )

    signed = False
    if not no_sign:
        key_path = Path(attestation_key_path or config.attestation_key_path or DEFAULT_KEY_PATH)
        if not key_path.exists():
            raise HaltProofError(
                f"attestation signing key not found at {key_path}; run 'haltproof keygen' first, "
                "or explicitly skip signing (not recommended)."
            )
        private_key = load_private_key(key_path)
        record = sign_record(record, private_key)
        signed = True

    attestation_log.append(record)

    remote_url = remote_collector_url or config.remote_collector_url
    remote_status = None
    if remote_url:
        remote_status = _post_to_collector(remote_url, record.to_dict())

    result = record.to_dict()
    result["signed"] = signed
    result["attestation_log_path"] = str(log_path)
    if remote_status is not None:
        result["remote_collector_status"] = remote_status
    result["any_failures"] = any(s.status.value == "failure" for s in all_steps)
    return result


def run_verify(
    *,
    attestation_ref: str,
    attestation_log_path: str | None = None,
    trusted_key_path: str | None = None,
) -> dict:
    """Verify an attestation record's signature and return its timeline."""
    ref_path = Path(attestation_ref)
    if ref_path.exists():
        record = load_record_from_file(ref_path)
    else:
        log_path = Path(attestation_log_path or DEFAULT_ATTESTATION_LOG)
        attestation_log = AttestationLog(log_path)
        record = attestation_log.find(attestation_ref)
        if record is None:
            raise HaltProofError(f"no attestation found matching {attestation_ref!r} in {log_path}")

    trusted_key = load_public_key(trusted_key_path) if trusted_key_path else None

    try:
        verify_record(record, trusted_public_key=trusted_key)
        valid = True
        error = None
    except (SignatureVerificationError, AttestationError) as exc:
        valid = False
        error = str(exc)

    return {"valid": valid, "error": error, "record": record.to_dict()}


def run_verify_chain(*, attestation_log_path: str | None = None) -> dict:
    """Verify an attestation log's full hash chain, not just one record.

    Confirms every record's own signature, that sequence numbers have no
    gaps, and that each record's ``prev_hash`` matches the content hash of
    the record before it -- catching a deleted or reordered record that a
    single-record signature check cannot.
    """
    log_path = Path(attestation_log_path or DEFAULT_ATTESTATION_LOG)
    attestation_log = AttestationLog(log_path)
    records = attestation_log.read_all()
    valid, error = attestation_log.verify_chain()
    return {
        "valid": valid,
        "error": error,
        "record_count": len(records),
        "attestation_log_path": str(log_path),
    }


def run_status(
    *,
    backend_name: str | None = None,
    nodes: list[str] | None = None,
    target_group: str | None = None,
    config_path: str | None = None,
) -> dict:
    """Report backend auto-detection results and optional target-group health."""
    config = load_config(config_path)

    available = detect_available_backends()
    detected = detect_backend()

    node_list = nodes
    if node_list is None and target_group:
        node_list = config.resolve_group(target_group)

    node_statuses = []
    active_backend_name = None
    if node_list:
        active_backend_name = resolve_backend_name(backend_name, config)
        backend = _build_backend(active_backend_name, config)
        node_statuses = [n.to_dict() for n in backend.status(node_list)]

    return {
        "available_backends": available,
        "auto_detected_backend": detected,
        "active_backend": active_backend_name,
        "nodes": node_statuses,
    }


def run_keygen(*, output_path: str | None = None, force: bool = False) -> dict:
    """Generate an Ed25519 attestation signing keypair."""
    key_path = Path(output_path or DEFAULT_KEY_PATH)

    if key_path.exists() and not force:
        raise HaltProofError(f"{key_path} already exists; pass force=True to overwrite.")

    public_key_path = generate_keypair(key_path)

    return {
        "private_key_path": str(key_path),
        "public_key_path": str(public_key_path),
        "private_key_permissions": "0600",
    }
