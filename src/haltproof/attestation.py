"""Signed attestation records for HaltProof halt operations.

Every halt operation, dry-run or real, produces one attestation record
describing what was targeted, what commands ran (or would run), per-node
outcomes, and who authorized it. Records are signed with Ed25519 and
appended as newline-delimited JSON to a local append-only log file. The
signing public key is embedded in each record (public keys are, by
definition, not secret) so ``verify`` can check a record's internal
consistency on its own; callers that need to confirm the record was signed
by a *specific trusted* operator key pass that key in explicitly.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from haltproof.backends.base import StepResult

SCHEMA_VERSION = 1


class AttestationError(Exception):
    """Raised for malformed attestation records."""


class SignatureVerificationError(Exception):
    """Raised when an attestation record's signature does not verify."""


@dataclass
class AttestationRecord:
    version: int
    id: str
    seq: int
    timestamp: str
    operator: str
    hostname: str
    action: str
    target_group: str
    backend: str
    nodes: list[str]
    dry_run: bool
    confirmed: bool
    steps: list[dict]
    summary: dict
    public_key: str = ""
    signature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AttestationRecord":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def _canonical_bytes(record_dict: dict) -> bytes:
    """Serialize a record (minus its signature) deterministically for signing."""
    payload = {k: v for k, v in record_dict.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_record(
    *,
    seq: int,
    operator: str,
    action: str,
    target_group: str,
    backend: str,
    nodes: list[str],
    dry_run: bool,
    confirmed: bool,
    steps: list[StepResult],
) -> AttestationRecord:
    """Build an unsigned attestation record from a halt operation's results."""
    step_dicts = [s.to_dict() if isinstance(s, StepResult) else s for s in steps]
    summary = {
        "success": sum(1 for s in step_dicts if s["status"] == "success"),
        "failure": sum(1 for s in step_dicts if s["status"] == "failure"),
        "planned": sum(1 for s in step_dicts if s["status"] == "planned"),
        "skipped": sum(1 for s in step_dicts if s["status"] == "skipped"),
    }
    return AttestationRecord(
        version=SCHEMA_VERSION,
        id=str(uuid.uuid4()),
        seq=seq,
        timestamp=datetime.now(timezone.utc).isoformat(),
        operator=operator,
        hostname=socket.gethostname(),
        action=action,
        target_group=target_group,
        backend=backend,
        nodes=nodes,
        dry_run=dry_run,
        confirmed=confirmed,
        steps=step_dicts,
        summary=summary,
    )


def sign_record(record: AttestationRecord, private_key: Ed25519PrivateKey) -> AttestationRecord:
    """Return a copy of ``record`` with ``public_key`` and ``signature`` set."""
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    record.public_key = base64.b64encode(public_bytes).decode("ascii")
    signing_payload = _canonical_bytes(record.to_dict())
    signature = private_key.sign(signing_payload)
    record.signature = base64.b64encode(signature).decode("ascii")
    return record


def verify_record(
    record: dict | AttestationRecord,
    trusted_public_key: Ed25519PublicKey | None = None,
) -> bool:
    """Verify a record's Ed25519 signature.

    If ``trusted_public_key`` is given, the record's embedded public key
    must also match it byte-for-byte — this is what lets a verifier confirm
    a record was signed by a *specific known* operator key, not merely by
    *some* Ed25519 key. Raises ``SignatureVerificationError`` on any
    mismatch (including a tampered field) and ``AttestationError`` for a
    structurally invalid record.
    """
    data = record.to_dict() if isinstance(record, AttestationRecord) else dict(record)

    signature_b64 = data.get("signature")
    public_key_b64 = data.get("public_key")
    if not signature_b64 or not public_key_b64:
        raise AttestationError("record is missing 'signature' or 'public_key'")

    try:
        public_key_bytes = base64.b64decode(public_key_b64)
        signature_bytes = base64.b64decode(signature_b64)
    except Exception as exc:
        raise AttestationError(f"malformed base64 in record: {exc}") from exc

    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except Exception as exc:
        raise AttestationError(f"invalid Ed25519 public key: {exc}") from exc

    if trusted_public_key is not None:
        trusted_bytes = trusted_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        if trusted_bytes != public_key_bytes:
            raise SignatureVerificationError(
                "record's embedded public key does not match the trusted key provided"
            )

    signing_payload = _canonical_bytes(data)
    try:
        public_key.verify(signature_bytes, signing_payload)
    except InvalidSignature as exc:
        raise SignatureVerificationError("signature does not match record contents") from exc

    return True


class AttestationLog:
    """Append-only newline-delimited-JSON attestation log with a monotonic sequence."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def next_seq(self) -> int:
        last = self._last_record()
        return (last["seq"] + 1) if last else 1

    def _last_record(self) -> dict | None:
        if not self.path.exists():
            return None
        last_line = None
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    last_line = line
        if last_line is None:
            return None
        return json.loads(last_line)

    def append(self, record: AttestationRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
        # Open in append mode with an exclusive advisory lock where available,
        # so concurrent halts writing to the same log file don't interleave
        # partial lines.
        with self.path.open("a", encoding="utf-8") as fh:
            try:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            except ImportError:
                pass  # fcntl is POSIX-only; Windows falls back to unlocked append.
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read_all(self) -> list[AttestationRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(AttestationRecord.from_dict(json.loads(line)))
        return records

    def find(self, attestation_id: str) -> AttestationRecord | None:
        for record in self.read_all():
            if record.id == attestation_id or str(record.seq) == attestation_id:
                return record
        return None


def load_record_from_file(path: str | Path) -> AttestationRecord:
    """Load a single attestation record from a file.

    Accepts either a file containing exactly one JSON record, or an NDJSON
    log file, in which case the last record in the file is returned.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise AttestationError(f"{path} is empty")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return AttestationRecord.from_dict(json.loads(lines[-1]))
