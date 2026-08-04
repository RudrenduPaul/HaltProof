from __future__ import annotations

from haltproof.operator import resolve_operator_id


def test_explicit_operator_id_wins(monkeypatch):
    monkeypatch.setenv("HALTPROOF_SSH_CERT_IDENTITY", "cert-user")
    assert resolve_operator_id("explicit-user") == "explicit-user"


def test_ssh_cert_identity_used_when_no_explicit_id(monkeypatch):
    monkeypatch.setenv("HALTPROOF_SSH_CERT_IDENTITY", "cert-user")
    assert resolve_operator_id(None) == "cert-user"


def test_falls_back_to_os_user(monkeypatch):
    monkeypatch.delenv("HALTPROOF_SSH_CERT_IDENTITY", raising=False)
    monkeypatch.setattr("getpass.getuser", lambda: "os-user")
    assert resolve_operator_id(None) == "os-user"
