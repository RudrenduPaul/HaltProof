from __future__ import annotations

import json
from unittest.mock import patch

from click.testing import CliRunner

from haltproof.backends.base import NodeStatus, StepResult, StepStatus
from haltproof.cli import cli


def _fake_drain(nodes, dry_run, reason):
    return [StepResult(node=n, operation="drain", command=["kubectl", "cordon", n], status=StepStatus.PLANNED) for n in nodes]


def _fake_noop(nodes, dry_run=None, **_):
    return [StepResult(node=n, operation="noop", command=[], status=StepStatus.SKIPPED, detail="n/a") for n in nodes]


def test_halt_dry_run_is_default_and_json_output_is_valid(tmp_path, signing_key_path):
    runner = CliRunner()
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=_fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        result = runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1,node-2",
                "--backend",
                "kubernetes",
                "--attestation-log",
                str(tmp_path / "att.jsonl"),
                "--attestation-key",
                str(signing_key_path),
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["dry_run"] is True
    assert data["confirmed"] is False
    assert data["signed"] is True
    assert data["backend"] == "kubernetes"
    assert all(s["status"] in ("planned", "skipped") for s in data["steps"])


def test_halt_requires_confirm_to_actually_execute(tmp_path, signing_key_path):
    runner = CliRunner()
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain") as mock_drain, \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        mock_drain.side_effect = _fake_drain
        runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--attestation-log",
                str(tmp_path / "att.jsonl"),
                "--attestation-key",
                str(signing_key_path),
                "--json",
            ],
        )
        # dry_run should have been passed True since --confirm was not given
        _, kwargs = mock_drain.call_args
        assert kwargs["dry_run"] is True


def test_halt_confirm_passes_dry_run_false(tmp_path, signing_key_path):
    runner = CliRunner()
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain") as mock_drain, \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        mock_drain.side_effect = lambda nodes, dry_run, reason: [
            StepResult(node=n, operation="drain", command=["kubectl", "cordon", n], status=StepStatus.SUCCESS)
            for n in nodes
        ]
        runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--confirm",
                "--attestation-log",
                str(tmp_path / "att.jsonl"),
                "--attestation-key",
                str(signing_key_path),
                "--json",
            ],
        )
        _, kwargs = mock_drain.call_args
        assert kwargs["dry_run"] is False


def test_halt_without_nodes_or_group_errors(tmp_path, signing_key_path):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "halt",
            "unknown-group",
            "--backend",
            "kubernetes",
            "--attestation-log",
            str(tmp_path / "att.jsonl"),
            "--attestation-key",
            str(signing_key_path),
        ],
    )
    assert result.exit_code != 0
    assert "no nodes resolved" in result.output


def test_verify_json_round_trip(tmp_path, signing_key_path):
    runner = CliRunner()
    log_path = tmp_path / "att.jsonl"
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=_fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        halt_result = runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--attestation-log",
                str(log_path),
                "--attestation-key",
                str(signing_key_path),
                "--json",
            ],
        )
    attestation_id = json.loads(halt_result.output)["id"]

    verify_result = runner.invoke(
        cli, ["verify", attestation_id, "--attestation-log", str(log_path), "--json"]
    )

    assert verify_result.exit_code == 0, verify_result.output
    verify_data = json.loads(verify_result.output)
    assert verify_data["valid"] is True
    assert verify_data["record"]["id"] == attestation_id


def test_verify_tampered_file_fails(tmp_path, signing_key_path):
    runner = CliRunner()
    log_path = tmp_path / "att.jsonl"
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=_fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--attestation-log",
                str(log_path),
                "--attestation-key",
                str(signing_key_path),
                "--json",
            ],
        )

    contents = log_path.read_text()
    tampered = contents.replace('"confirmed":false', '"confirmed":true')
    log_path.write_text(tampered)

    verify_result = runner.invoke(cli, ["verify", "1", "--attestation-log", str(log_path), "--json"])
    verify_data = json.loads(verify_result.output)
    assert verify_data["valid"] is False
    assert verify_result.exit_code == 1


def test_status_json_shape():
    runner = CliRunner()
    with patch(
        "haltproof.core.detect_available_backends",
        return_value={"kubernetes": True, "slurm": False, "ipmi": False},
    ), patch("haltproof.core.detect_backend", return_value="kubernetes"):
        result = runner.invoke(cli, ["status", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["auto_detected_backend"] == "kubernetes"
    assert set(data["available_backends"]) == {"kubernetes", "slurm", "ipmi"}


def test_status_with_nodes_reports_health():
    runner = CliRunner()
    fake_status = [NodeStatus(node="node-1", reachable=True, state="ready")]
    with patch("haltproof.core.detect_available_backends", return_value={"kubernetes": True, "slurm": False, "ipmi": False}), \
         patch("haltproof.core.detect_backend", return_value="kubernetes"), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.status", return_value=fake_status):
        result = runner.invoke(cli, ["status", "--nodes", "node-1", "--json"])

    data = json.loads(result.output)
    assert data["nodes"][0]["node"] == "node-1"
    assert data["nodes"][0]["state"] == "ready"


def test_keygen_creates_key_and_never_prints_private_material(tmp_path):
    runner = CliRunner()
    key_path = tmp_path / "newkey"
    result = runner.invoke(cli, ["keygen", "--output", str(key_path), "--json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["private_key_path"] == str(key_path)
    # The raw PEM header must never appear in CLI output.
    assert "BEGIN PRIVATE KEY" not in result.output


def test_keygen_refuses_to_overwrite_without_force(tmp_path):
    runner = CliRunner()
    key_path = tmp_path / "newkey"
    runner.invoke(cli, ["keygen", "--output", str(key_path)])
    result = runner.invoke(cli, ["keygen", "--output", str(key_path)])

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_keygen_human_output_never_prints_private_material(tmp_path):
    runner = CliRunner()
    key_path = tmp_path / "newkey"
    result = runner.invoke(cli, ["keygen", "--output", str(key_path)])

    assert result.exit_code == 0
    assert "BEGIN PRIVATE KEY" not in result.output
    assert "keygen generated" in result.output.lower() or "keypair generated" in result.output.lower()


def test_halt_human_output_and_status_human_output(tmp_path, signing_key_path):
    runner = CliRunner()
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=_fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        halt_result = runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--attestation-log",
                str(tmp_path / "att.jsonl"),
                "--attestation-key",
                str(signing_key_path),
            ],
        )

    assert halt_result.exit_code == 0
    assert "DRY-RUN" in halt_result.output
    assert "attestation id=" in halt_result.output

    verify_result = runner.invoke(
        cli, ["verify", "1", "--attestation-log", str(tmp_path / "att.jsonl")]
    )
    assert verify_result.exit_code == 0
    assert "VALID SIGNATURE" in verify_result.output
    assert "timeline:" in verify_result.output

    with patch("haltproof.core.detect_available_backends", return_value={"kubernetes": True, "slurm": False, "ipmi": False}), \
         patch("haltproof.core.detect_backend", return_value="kubernetes"):
        status_result = runner.invoke(cli, ["status"])
    assert status_result.exit_code == 0
    assert "Backend availability" in status_result.output


def test_halt_no_sign_skips_signature(tmp_path):
    runner = CliRunner()
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=_fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        result = runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--no-sign",
                "--attestation-log",
                str(tmp_path / "att.jsonl"),
                "--json",
            ],
        )

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["signed"] is False
    assert data["signature"] == ""


def test_halt_missing_signing_key_errors_clearly(tmp_path):
    runner = CliRunner()
    with patch("haltproof.backends.kubernetes.KubernetesBackend.drain", side_effect=_fake_drain), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.isolate_network", side_effect=_fake_noop), \
         patch("haltproof.backends.kubernetes.KubernetesBackend.power_fence", side_effect=_fake_noop):
        result = runner.invoke(
            cli,
            [
                "halt",
                "gpu-pod-a",
                "--nodes",
                "node-1",
                "--backend",
                "kubernetes",
                "--attestation-log",
                str(tmp_path / "att.jsonl"),
                "--attestation-key",
                str(tmp_path / "does-not-exist-key"),
            ],
        )

    assert result.exit_code != 0
    assert "haltproof keygen" in result.output
