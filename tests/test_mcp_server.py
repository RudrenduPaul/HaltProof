from __future__ import annotations

import asyncio
import json as json_module
from unittest.mock import patch

from haltproof import mcp_server
from haltproof.backends.base import StepResult, StepStatus


def test_all_four_tools_are_registered():
    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {"halt", "verify", "status", "keygen"}


def test_keygen_tool_returns_paths_not_key_material(tmp_path):
    key_path = tmp_path / "mcpkey"
    result = mcp_server.keygen(output_path=str(key_path))

    assert result["private_key_path"] == str(key_path)
    assert "BEGIN PRIVATE KEY" not in json_module.dumps(result)


def test_status_tool_delegates_to_core():
    with patch(
        "haltproof.core.detect_available_backends",
        return_value={"kubernetes": True, "slurm": False, "ipmi": False},
    ), patch("haltproof.core.detect_backend", return_value="kubernetes"):
        result = mcp_server.status()

    assert result["auto_detected_backend"] == "kubernetes"


def test_halt_tool_defaults_to_dry_run(tmp_path, signing_key_path):
    def fake_drain(nodes, dry_run, reason):
        return [StepResult(node=n, operation="drain", command=["x"], status=StepStatus.PLANNED) for n in nodes]

    def fake_noop(nodes, dry_run=None, **_):
        return [StepResult(node=n, operation="noop", command=[], status=StepStatus.SKIPPED) for n in nodes]

    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=fake_noop), \
         patch("haltproof.core.DEFAULT_ATTESTATION_LOG", tmp_path / "att.jsonl"), \
         patch("haltproof.core.DEFAULT_KEY_PATH", signing_key_path):
        result = mcp_server.halt(target_group="gpu-pod-a", nodes=["node-1"], backend="kubernetes")

    assert result["dry_run"] is True
    assert result["confirmed"] is False


def test_halt_tool_reports_error_dict_on_unknown_group(tmp_path):
    result = mcp_server.halt(target_group="does-not-exist", nodes=None, backend="kubernetes")
    assert "error" in result


def test_verify_tool_reports_error_for_missing_attestation():
    result = mcp_server.verify(attestation_ref="nonexistent-id-123")
    assert "error" in result
