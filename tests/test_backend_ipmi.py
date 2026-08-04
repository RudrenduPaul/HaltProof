from __future__ import annotations

import os
from unittest.mock import patch

from haltproof.backends.base import StepStatus
from haltproof.backends.ipmi import IpmiBackend


def _completed(returncode=0, stdout="", stderr=""):
    class _Result:
        pass

    r = _Result()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_power_fence_dry_run_builds_command_without_running():
    backend = IpmiBackend(user="admin")
    with patch("haltproof.backends.runner.subprocess.run") as mock_run:
        results = backend.power_fence(["bmc-1.example.com"], dry_run=True)

    mock_run.assert_not_called()
    assert results[0].status == StepStatus.PLANNED
    command = results[0].command
    assert command[:4] == ["ipmitool", "-I", "lanplus", "-H"]
    assert "bmc-1.example.com" in command
    assert command[-3:] == ["chassis", "power", "off"]


def test_power_fence_never_puts_password_in_command_line():
    backend = IpmiBackend(user="admin")
    with patch.dict(os.environ, {"IPMI_PASSWORD": "super-secret-value"}):
        with patch("haltproof.backends.runner.subprocess.run") as mock_run:
            results = backend.power_fence(["bmc-1"], dry_run=True)

    command_str = " ".join(results[0].command)
    assert "super-secret-value" not in command_str
    assert "-E" in results[0].command
    mock_run.assert_not_called()


def test_power_fence_confirm_runs_ipmitool_and_reports_success():
    backend = IpmiBackend(user="admin")
    with patch("haltproof.backends.runner.subprocess.run", return_value=_completed(0, "Chassis Power Control: Down/Off")):
        results = backend.power_fence(["bmc-1"], dry_run=False)

    assert results[0].status == StepStatus.SUCCESS


def test_drain_and_isolate_network_are_skipped_with_guidance():
    backend = IpmiBackend()

    drain_results = backend.drain(["bmc-1"], dry_run=True, reason="n/a")
    isolate_results = backend.isolate_network(["bmc-1"], dry_run=True)

    assert drain_results[0].status == StepStatus.SKIPPED
    assert "slurm" in drain_results[0].detail.lower() or "kubernetes" in drain_results[0].detail.lower()
    assert isolate_results[0].status == StepStatus.SKIPPED


def test_status_parses_power_state():
    backend = IpmiBackend(user="admin")
    with patch("haltproof.backends.ipmi.subprocess.run", return_value=_completed(0, "Chassis Power is on")):
        statuses = backend.status(["bmc-1"])

    assert statuses[0].state == "on"
    assert statuses[0].reachable is True


def test_status_handles_ipmitool_not_found():
    backend = IpmiBackend()
    with patch("haltproof.backends.ipmi.subprocess.run", side_effect=FileNotFoundError()):
        statuses = backend.status(["bmc-1"])

    assert statuses[0].reachable is False
