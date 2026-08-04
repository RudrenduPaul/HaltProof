from __future__ import annotations

from pathlib import Path

import haltproof.config as config_module
from haltproof.config import load_config


def test_load_config_reads_groups_and_backend(tmp_path):
    config_file = tmp_path / "haltproof.toml"
    config_file.write_text(
        """
backend = "kubernetes"
operator_id = "ops-team"

[groups]
gpu-pod-a = ["node-1", "node-2"]

[kubernetes]
namespace = "training"
"""
    )

    config = load_config(str(config_file))

    assert config.backend == "kubernetes"
    assert config.operator_id == "ops-team"
    assert config.resolve_group("gpu-pod-a") == ["node-1", "node-2"]
    assert config.resolve_group("does-not-exist") is None
    assert config.namespace == "training"


def test_load_config_returns_defaults_when_no_file_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HALTPROOF_CONFIG", raising=False)
    monkeypatch.setattr(
        config_module, "DEFAULT_LOCATIONS", [Path("haltproof.toml"), tmp_path / "unused" / "config.toml"]
    )

    config = load_config()

    assert config.backend is None
    assert config.resolve_group("anything") is None
    assert config.namespace == "default"
