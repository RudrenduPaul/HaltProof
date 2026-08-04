from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from haltproof.attestation import (
    AttestationError,
    AttestationLog,
    SignatureVerificationError,
    build_record,
    record_content_hash,
    sign_record,
    verify_chain,
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


def _append_chained(log, private_key, *, operator="alice"):
    """Append one properly hash-chained, signed record and return it."""
    seq, prev_hash = log.chain_state()
    record = sign_record(
        build_record(
            seq=seq,
            operator=operator,
            action="halt",
            target_group="grp",
            backend="slurm",
            nodes=["node-1"],
            dry_run=True,
            confirmed=False,
            steps=_make_steps(),
            prev_hash=prev_hash,
        ),
        private_key,
    )
    log.append(record)
    return record


def test_record_content_hash_changes_with_any_field(private_key):
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
    original_hash = record_content_hash(signed)

    tampered = signed.to_dict()
    tampered["operator"] = "mallory"
    assert record_content_hash(tampered) != original_hash


def test_chain_state_progression(tmp_path, private_key):
    log = AttestationLog(tmp_path / "attestations.jsonl")

    seq, prev_hash = log.chain_state()
    assert (seq, prev_hash) == (1, "")

    first = _append_chained(log, private_key)
    seq, prev_hash = log.chain_state()
    assert seq == 2
    assert prev_hash == record_content_hash(first)


def test_verify_chain_accepts_intact_chain(tmp_path, private_key):
    log = AttestationLog(tmp_path / "attestations.jsonl")
    for _ in range(3):
        _append_chained(log, private_key)

    valid, error = log.verify_chain()
    assert valid is True
    assert error is None


def test_verify_chain_empty_log_is_valid(tmp_path):
    log = AttestationLog(tmp_path / "attestations.jsonl")
    assert log.verify_chain() == (True, None)


def test_verify_chain_detects_deleted_record(tmp_path, private_key):
    log = AttestationLog(tmp_path / "attestations.jsonl")
    for _ in range(3):
        _append_chained(log, private_key)

    records = log.read_all()
    # Simulate an attacker (or the operator) deleting the middle record
    # directly from the log file -- the remaining two records' own
    # signatures still verify individually.
    remaining = [records[0], records[2]]

    valid, error = verify_chain(remaining)
    assert valid is False
    assert "sequence gap" in error


def test_verify_chain_detects_tampered_prev_hash(tmp_path, private_key):
    # prev_hash is part of a record's own signed payload, so mutating it
    # after signing breaks that record's signature too (a stronger property
    # than a naive chain check would give). To isolate the "signature is
    # intact but the chain link doesn't match" case, sign a second record
    # with a wrong-but-well-formed prev_hash baked in from the start, as if
    # it were spliced in from a different log.
    log = AttestationLog(tmp_path / "attestations.jsonl")
    first = _append_chained(log, private_key)
    assert first  # keep the first record's chain state out of the splice below

    spliced = sign_record(
        build_record(
            seq=2,
            operator="alice",
            action="halt",
            target_group="grp",
            backend="slurm",
            nodes=["node-1"],
            dry_run=True,
            confirmed=False,
            steps=_make_steps(),
            prev_hash="0" * 64,
        ),
        private_key,
    )
    log.append(spliced)

    valid, error = log.verify_chain()
    assert valid is False
    assert "prev_hash" in error


def test_verify_chain_rejects_first_record_with_nonempty_prev_hash(private_key):
    record = sign_record(
        build_record(
            seq=1,
            operator="alice",
            action="halt",
            target_group="grp",
            backend="slurm",
            nodes=["node-1"],
            dry_run=True,
            confirmed=False,
            steps=_make_steps(),
            prev_hash="not-empty",
        ),
        private_key,
    )

    valid, error = verify_chain([record])
    assert valid is False
    assert "first record" in error


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
