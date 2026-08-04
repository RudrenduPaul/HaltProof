"""Ed25519 keypair generation and loading for attestation signing."""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PRIVATE_KEY_MODE = 0o600


def generate_keypair(private_key_path: str | Path) -> Path:
    """Generate an Ed25519 keypair and write it to disk.

    The private key is written to ``private_key_path`` with permissions
    0600 (owner read/write only) so it is never world- or group-readable.
    The public key is written alongside it at ``<private_key_path>.pub``.

    Returns the path to the public key. The private key material is never
    returned, logged, or printed by this function or any caller.
    """
    private_key_path = Path(private_key_path)
    public_key_path = private_key_path.with_suffix(private_key_path.suffix + ".pub")

    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    private_key_path.parent.mkdir(parents=True, exist_ok=True)

    # Create with restrictive permissions from the start rather than
    # chmod-ing after the fact, so the key is never briefly world-readable.
    fd = os.open(
        str(private_key_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, PRIVATE_KEY_MODE
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(private_bytes)
    finally:
        os.chmod(private_key_path, PRIVATE_KEY_MODE)

    public_key_path.write_bytes(public_bytes)
    os.chmod(public_key_path, 0o644)

    return public_key_path


def load_private_key(private_key_path: str | Path) -> Ed25519PrivateKey:
    data = Path(private_key_path).read_bytes()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{private_key_path} is not an Ed25519 private key")
    return key


def load_public_key(public_key_path: str | Path) -> Ed25519PublicKey:
    data = Path(public_key_path).read_bytes()
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(f"{public_key_path} is not an Ed25519 public key")
    return key
