from __future__ import annotations

from unittest.mock import patch

from haltproof.backends.base import StepStatus
from haltproof.backends.slurm import SlurmBackend


def _completed(returncode=0, stdout="", stderr=""):
    class _Result:
        pass

    r = _Result()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_drain_dry_run_builds_scontrol_command_without_running():
    backend = SlurmBackend()
    with patch("haltproof.backends.runner.subprocess.run") as mock_run:
        results = backend.drain(["node-1"], dry_run=True, reason="incident-7")

    mock_run.assert_not_called()
    assert results[0].status == StepStatus.PLANNED
    assert results[0].command == [
        "scontrol",
        "update",
        "nodename=node-1",
        "state=drain",
        "reason=incident-7",
    ]


def test_drain_confirm_runs_scontrol_and_reports_success():
    backend = SlurmBackend()
    with patch("haltproof.backends.runner.subprocess.run", return_value=_completed(0)) as mock_run:
        results = backend.drain(["node-1", "node-2"], dry_run=False, reason="incident-7")

    assert mock_run.call_count == 2
    assert all(r.status == StepStatus.SUCCESS for r in results)


def test_isolate_network_uses_power_down_suspend_hook():
    backend = SlurmBackend()
    with patch("haltproof.backends.runner.subprocess.run") as mock_run:
        results = backend.isolate_network(["node-1"], dry_run=True)

    mock_run.assert_not_called()
    assert results[0].operation == "suspend"
    assert results[0].command == ["scontrol", "update", "nodename=node-1", "state=power_down"]


def test_power_fence_is_skipped_with_ipmi_guidance():
    backend = SlurmBackend()
    results = backend.power_fence(["node-1"], dry_run=True)

    assert results[0].status == StepStatus.SKIPPED
    assert "ipmi" in results[0].detail.lower()


def test_status_parses_state_token():
    backend = SlurmBackend()
    with patch(
        "haltproof.backends.slurm.subprocess.run",
        return_value=_completed(0, "NodeName=node-1 State=DRAINED Reason=none"),
    ):
        statuses = backend.status(["node-1"])

    assert statuses[0].state == "drained"
    assert statuses[0].reachable is True


def test_status_handles_scontrol_not_found():
    backend = SlurmBackend()
    with patch("haltproof.backends.slurm.subprocess.run", side_effect=FileNotFoundError()):
        statuses = backend.status(["node-1"])

    assert statuses[0].reachable is False
