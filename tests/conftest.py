from __future__ import annotations

import pytest

from haltproof.keys import generate_keypair, load_private_key


@pytest.fixture()
def signing_key_path(tmp_path):
    key_path = tmp_path / "ed25519_key"
    generate_keypair(key_path)
    return key_path


@pytest.fixture()
def private_key(signing_key_path):
    return load_private_key(signing_key_path)
