"""MCP server exposing HaltProof's operations as tools for AI agents.

Built on the official ``mcp`` Python SDK's high-level ``MCPServer``
interface. Every tool here is a thin wrapper over :mod:`haltproof.core`,
the same functions the CLI calls, so an agent invoking HaltProof over MCP
gets identical behavior (including dry-run-by-default gating on ``halt``)
to a human running the CLI directly.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from haltproof import core

mcp = MCPServer("haltproof")


@mcp.tool()
def halt(
    target_group: str,
    nodes: list[str] | None = None,
    backend: str | None = None,
    confirm: bool = False,
    reason: str = "haltproof halt requested",
    operator_id: str | None = None,
) -> dict[str, Any]:
    """Drain, isolate, and power-fence a target node group.

    Dry-run is the default: pass confirm=True to actually execute the
    halt. Without confirm=True, this reports exactly what commands would
    run against which nodes, in what order, without running them.
    """
    try:
        return core.run_halt(
            target_group=target_group,
            nodes=nodes,
            backend_name=backend,
            confirm=confirm,
            reason=reason,
            operator_id=operator_id,
        )
    except core.HaltProofError as exc:
        return {"error": str(exc)}


@mcp.tool()
def verify(
    attestation_ref: str,
    attestation_log_path: str | None = None,
    trusted_key_path: str | None = None,
) -> dict[str, Any]:
    """Verify an attestation record's Ed25519 signature and return its timeline.

    attestation_ref is either a path to a file containing the record, or an
    attestation id / sequence number to look up in the attestation log.
    """
    try:
        return core.run_verify(
            attestation_ref=attestation_ref,
            attestation_log_path=attestation_log_path,
            trusted_key_path=trusted_key_path,
        )
    except core.HaltProofError as exc:
        return {"error": str(exc)}


@mcp.tool()
def status(
    backend: str | None = None,
    nodes: list[str] | None = None,
    group: str | None = None,
) -> dict[str, Any]:
    """Report backend auto-detection results and optional target-group health."""
    try:
        return core.run_status(backend_name=backend, nodes=nodes, target_group=group)
    except core.HaltProofError as exc:
        return {"error": str(exc)}


@mcp.tool()
def keygen(output_path: str | None = None, force: bool = False) -> dict[str, Any]:
    """Generate an Ed25519 keypair for attestation signing.

    Returns only file paths and permission metadata. Private key material
    is never returned, logged, or included in the tool result.
    """
    try:
        return core.run_keygen(output_path=output_path, force=force)
    except core.HaltProofError as exc:
        return {"error": str(exc)}


def run_server() -> None:
    """Start the MCP server on stdio transport."""
    mcp.run(transport="stdio")
