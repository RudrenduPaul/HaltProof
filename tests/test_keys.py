from __future__ import annotations

import stat

from haltproof.keys import generate_keypair, load_private_key, load_public_key


def test_generate_keypair_writes_private_key_with_0600_permissions(tmp_path):
    key_path = tmp_path / "subdir" / "key"
    public_key_path = generate_keypair(key_path)

    mode = stat.S_IMODE(key_path.stat().st_mode)
    assert mode == 0o600
    assert public_key_path == key_path.with_suffix(".pub")
    assert public_key_path.exists()


def test_generated_keys_are_loadable_and_paired(tmp_path):
    key_path = tmp_path / "key"
    public_key_path = generate_keypair(key_path)

    private_key = load_private_key(key_path)
    public_key = load_public_key(public_key_path)

    assert private_key.public_key().public_bytes_raw() == public_key.public_bytes_raw()


def test_generate_keypair_never_returns_private_key_material(tmp_path):
    key_path = tmp_path / "key"
    result = generate_keypair(key_path)

    # The function's return value must only ever be a path, never key bytes.
    assert isinstance(result, type(key_path))
