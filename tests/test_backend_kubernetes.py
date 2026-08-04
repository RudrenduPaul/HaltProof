from __future__ import annotations

import json
from unittest.mock import patch

from haltproof.backends.base import StepStatus
from haltproof.backends.kubernetes import KubernetesBackend


def _completed(returncode=0, stdout="", stderr=""):
    class _Result:
        pass

    r = _Result()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_drain_dry_run_does_not_invoke_subprocess():
    backend = KubernetesBackend()
    with patch("haltproof.backends.runner.subprocess.run") as mock_run:
        results = backend.drain(["node-1"], dry_run=True, reason="test")

    mock_run.assert_not_called()
    assert all(r.status == StepStatus.PLANNED for r in results)
    # cordon then drain per node
    assert [r.operation for r in results] == ["cordon", "drain"]
    assert results[0].command == ["kubectl", "cordon", "node-1"]
    assert results[1].command[:3] == ["kubectl", "drain", "node-1"]


def test_drain_confirm_invokes_subprocess_and_reports_success():
    backend = KubernetesBackend()
    with patch("haltproof.backends.runner.subprocess.run", return_value=_completed(0, "cordoned")) as mock_run:
        results = backend.drain(["node-1", "node-2"], dry_run=False, reason="incident-42")

    assert mock_run.call_count == 4  # cordon+drain per node, 2 nodes
    assert all(r.status == StepStatus.SUCCESS for r in results)


def test_drain_confirm_reports_failure_on_nonzero_exit():
    backend = KubernetesBackend()
    with patch("haltproof.backends.runner.subprocess.run", return_value=_completed(1, "", "node not found")):
        results = backend.drain(["node-1"], dry_run=False, reason="incident-42")

    assert results[0].status == StepStatus.FAILURE
    assert "node not found" in results[0].detail


def test_isolate_network_dry_run_shows_manifest_without_running():
    backend = KubernetesBackend(namespace="prod")
    with patch("haltproof.backends.kubernetes.subprocess.run") as mock_run:
        results = backend.isolate_network(["node-1"], dry_run=True)

    mock_run.assert_not_called()
    assert results[0].status == StepStatus.PLANNED
    assert "NetworkPolicy" in results[0].detail
    assert "prod" in results[0].detail


def test_isolate_network_confirm_applies_manifest():
    backend = KubernetesBackend(namespace="default")
    with patch("haltproof.backends.kubernetes.subprocess.run", return_value=_completed(0, "networkpolicy applied")) as mock_run:
        results = backend.isolate_network(["node-1", "node-2"], dry_run=False)

    assert mock_run.call_count == 1  # one cluster-wide apply, not per node
    kwargs = mock_run.call_args.kwargs
    assert "NetworkPolicy" in kwargs["input"]
    assert all(r.status == StepStatus.SUCCESS for r in results)


def test_power_fence_is_skipped_with_explanation():
    backend = KubernetesBackend()
    results = backend.power_fence(["node-1"], dry_run=True)

    assert results[0].status == StepStatus.SKIPPED
    assert "ipmi" in results[0].detail.lower()
    assert results[0].command == []


def test_status_parses_ready_and_cordoned_state():
    backend = KubernetesBackend()
    ready_node = json.dumps(
        {"status": {"conditions": [{"type": "Ready", "status": "True"}]}, "spec": {}}
    )
    cordoned_node = json.dumps(
        {
            "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            "spec": {"unschedulable": True},
        }
    )

    with patch(
        "haltproof.backends.kubernetes.subprocess.run",
        side_effect=[_completed(0, ready_node), _completed(0, cordoned_node)],
    ):
        statuses = backend.status(["node-1", "node-2"])

    assert statuses[0].state == "ready"
    assert statuses[0].reachable is True
    assert statuses[1].state == "cordoned"


def test_status_handles_kubectl_not_found():
    backend = KubernetesBackend()
    with patch("haltproof.backends.kubernetes.subprocess.run", side_effect=FileNotFoundError()):
        statuses = backend.status(["node-1"])

    assert statuses[0].reachable is False
    assert statuses[0].state == "unknown"
