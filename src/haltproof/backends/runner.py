"""Shared subprocess execution helper used by every backend.

Centralizing this in one place means dry-run gating and error handling are
implemented once and tested once, instead of duplicated per backend.
"""

from __future__ import annotations

import subprocess

from haltproof.backends.base import StepResult, StepStatus


def run_step(
    node: str,
    operation: str,
    command: list[str],
    *,
    dry_run: bool,
    env: dict | None = None,
    timeout: float = 60.0,
) -> StepResult:
    """Run ``command`` for ``node``/``operation``, or report it as planned.

    Dry-run is enforced here, at the single chokepoint every backend routes
    through, rather than re-implemented in each backend's drain/isolate/fence
    method. Nothing destructive can execute without ``dry_run=False`` being
    explicitly passed all the way down from the CLI's ``--confirm`` flag.
    """
    if dry_run:
        return StepResult(
            node=node,
            operation=operation,
            command=command,
            status=StepStatus.PLANNED,
            detail="dry-run: command not executed",
        )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        return StepResult(
            node=node,
            operation=operation,
            command=command,
            status=StepStatus.FAILURE,
            detail=f"executable not found: {exc}",
        )
    except subprocess.TimeoutExpired as exc:
        return StepResult(
            node=node,
            operation=operation,
            command=command,
            status=StepStatus.FAILURE,
            detail=f"timed out after {exc.timeout}s",
        )

    if result.returncode == 0:
        return StepResult(
            node=node,
            operation=operation,
            command=command,
            status=StepStatus.SUCCESS,
            detail=result.stdout.strip()[:500],
        )

    return StepResult(
        node=node,
        operation=operation,
        command=command,
        status=StepStatus.FAILURE,
        detail=(result.stderr or result.stdout).strip()[:500],
    )


def skipped(node: str, operation: str, reason: str) -> StepResult:
    """Build a SKIPPED result for an operation a backend does not support."""
    return StepResult(
        node=node,
        operation=operation,
        command=[],
        status=StepStatus.SKIPPED,
        detail=reason,
    )
