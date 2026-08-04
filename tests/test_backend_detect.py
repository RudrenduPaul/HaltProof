from __future__ import annotations

from unittest.mock import patch

import pytest

from haltproof.backends.detect import detect_backend, get_backend, known_backend_names
from haltproof.backends.ipmi import IpmiBackend
from haltproof.backends.kubernetes import KubernetesBackend
from haltproof.backends.slurm import SlurmBackend


def _which_only(*present):
    def _fake_which(tool):
        mapping = {"kubectl": "kubernetes", "scontrol": "slurm", "ipmitool": "ipmi"}
        return f"/usr/bin/{tool}" if mapping.get(tool) in present else None

    return _fake_which


def test_detect_prefers_kubernetes_when_multiple_present():
    with patch("haltproof.backends.detect.shutil.which", side_effect=_which_only("kubernetes", "slurm", "ipmi")):
        assert detect_backend() == "kubernetes"


def test_detect_falls_back_to_slurm():
    with patch("haltproof.backends.detect.shutil.which", side_effect=_which_only("slurm", "ipmi")):
        assert detect_backend() == "slurm"


def test_detect_falls_back_to_ipmi():
    with patch("haltproof.backends.detect.shutil.which", side_effect=_which_only("ipmi")):
        assert detect_backend() == "ipmi"


def test_detect_returns_none_when_nothing_present():
    with patch("haltproof.backends.detect.shutil.which", side_effect=_which_only()):
        assert detect_backend() is None


def test_get_backend_returns_correct_class():
    assert isinstance(get_backend("kubernetes"), KubernetesBackend)
    assert isinstance(get_backend("slurm"), SlurmBackend)
    assert isinstance(get_backend("ipmi"), IpmiBackend)


def test_get_backend_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_backend("nonexistent")


def test_known_backend_names_covers_all_three():
    assert set(known_backend_names()) == {"kubernetes", "slurm", "ipmi"}
