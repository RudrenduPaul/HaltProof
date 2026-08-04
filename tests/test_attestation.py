from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from haltproof.attestation import (
    AttestationError,
    AttestationLog,
    SignatureVerificationError,
    build_record,
    sign_record,
    verify_record,
)
from haltproof.backends.base import StepResult, StepStatus
from haltproof.keys import load_public_key


def _make_steps():
    return [
        StepResult(
            node="node-1",
            operation="drain",
            command=["kubectl", "cordon", "node-1"],
            status=StepStatus.SUCCESS,
        ),
        StepResult(
            node="node-1",
            operation="power_fence",
            command=[],
            status=StepStatus.SKIPPED,
            detail="not supported",
        ),
    ]


def test_sign_and_verify_round_trip(private_key):
    record = build_record(
        seq=1,
        operator="alice",
        action="halt",
        target_group="gpu-pod-a",
        backend="kubernetes",
        nodes=["node-1"],
        dry_run=True,
        confirmed=False,
        steps=_make_steps(),
    )
    signed = sign_record(record, private_key)

    assert signed.signature
    assert signed.public_key
    assert verify_record(signed) is True


def test_verify_rejects_tampered_field(private_key):
    record = build_record(
        seq=1,
        operator="alice",
        action="halt",
        target_group="gpu-pod-a",
        backend="kubernetes",
        nodes=["node-1"],
        dry_run=True,
        confirmed=False,
        steps=_make_steps(),
    )
    signed = sign_record(record, private_key)
    tampered = signed.to_dict()
    tampered["operator"] = "mallory"  # attacker rewrites who authorized the halt

    with pytest.raises(SignatureVerificationError):
        verify_record(tampered)


def test_verify_rejects_tampered_steps(private_key):
    record = build_record(
        seq=1,
        operator="alice",
        action="halt",
        target_group="gpu-pod-a",
        backend="kubernetes",
        nodes=["node-1"],
        dry_run=False,
        confirmed=True,
        steps=_make_steps(),
    )
    signed = sign_record(record, private_key)
    tampered = signed.to_dict()
    tampered["steps"][0]["status"] = "failure"  # attacker hides a real failure

    with pytest.raises(SignatureVerificationError):
        verify_record(tampered)


def test_verify_with_trusted_key_mismatch_rejected(private_key):
    other_key = Ed25519PrivateKey.generate()
    record = build_record(
        seq=1,
        operator="alice",
        action="halt",
        target_group="grp",
        backend="slurm",
        nodes=["node-1"],
        dry_run=True,
        confirmed=False,
        steps=_make_steps(),
    )
    signed = sign_record(record, private_key)

    with pytest.raises(SignatureVerificationError):
        verify_record(signed, trusted_public_key=other_key.public_key())


def test_verify_with_matching_trusted_key_succeeds(private_key, signing_key_path):
    record = build_record(
        seq=1,
        operator="alice",
        action="halt",
        target_group="grp",
        backend="slurm",
        nodes=["node-1"],
        dry_run=True,
        confirmed=False,
        steps=_make_steps(),
    )
    signed = sign_record(record, private_key)
    trusted = load_public_key(str(signing_key_path) + ".pub")

    assert verify_record(signed, trusted_public_key=trusted) is True


def test_verify_raises_attestation_error_for_missing_signature():
    with pytest.raises(AttestationError):
        verify_record({"foo": "bar"})


def test_attestation_log_monotonic_sequence(tmp_path, private_key):
    log = AttestationLog(tmp_path / "attestations.jsonl")

    assert log.next_seq() == 1
    record1 = sign_record(
        build_record(
            seq=log.next_seq(),
            operator="alice",
            action="halt",
            target_group="grp",
            backend="slurm",
            nodes=["node-1"],
            dry_run=True,
            confirmed=False,
            steps=_make_steps(),
        ),
        private_key,
    )
    log.append(record1)

    assert log.next_seq() == 2
    record2 = sign_record(
        build_record(
            seq=log.next_seq(),
            operator="alice",
            action="halt",
            target_group="grp",
            backend="slurm",
            nodes=["node-1"],
            dry_run=True,
            confirmed=False,
            steps=_make_steps(),
        ),
        private_key,
    )
    log.append(record2)

    records = log.read_all()
    assert [r.seq for r in records] == [1, 2]
    assert records[0].id != records[1].id


def test_attestation_log_find_by_id_and_seq(tmp_path, private_key):
    log = AttestationLog(tmp_path / "attestations.jsonl")
    record = sign_record(
        build_record(
            seq=log.next_seq(),
            operator="alice",
            action="halt",
            target_group="grp",
            backend="slurm",
            nodes=["node-1"],
            dry_run=True,
            confirmed=False,
            steps=_make_steps(),
        ),
        private_key,
    )
    log.append(record)

    assert log.find(record.id).id == record.id
    assert log.find(str(record.seq)).id == record.id
    assert log.find("does-not-exist") is None


def test_log_file_is_valid_ndjson(tmp_path, private_key):
    log = AttestationLog(tmp_path / "attestations.jsonl")
    for _ in range(3):
        record = sign_record(
            build_record(
                seq=log.next_seq(),
                operator="alice",
                action="halt",
                target_group="grp",
                backend="slurm",
                nodes=["node-1"],
                dry_run=True,
                confirmed=False,
                steps=_make_steps(),
            ),
            private_key,
        )
        log.append(record)

    lines = (tmp_path / "attestations.jsonl").read_text().strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        json.loads(line)  # each line must be independently parseable JSON
