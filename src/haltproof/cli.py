"""HaltProof command-line interface.

Every command supports both a human-readable output format (the default)
and a structured ``--json`` / ``--format=json`` output, so the same CLI is
usable directly by an operator at a terminal and programmatically by an
automation script or agent. All commands are thin wrappers over
:mod:`haltproof.core`, which the MCP server also calls, so the two
transports can never drift apart in behavior.
"""

from __future__ import annotations

import json as json_module
import sys

import click

from haltproof import __version__, core

DEFAULT_ATTESTATION_LOG = core.DEFAULT_ATTESTATION_LOG
DEFAULT_KEY_PATH = core.DEFAULT_KEY_PATH


def _format_option(fn):
    fn = click.option("--json", "json_flag", is_flag=True, help="Shorthand for --format=json.")(fn)
    fn = click.option(
        "--format",
        "output_format",
        type=click.Choice(["human", "json"]),
        default="human",
        help="Output format.",
    )(fn)
    return fn


def _resolve_format(output_format: str, json_flag: bool) -> str:
    return "json" if (json_flag or output_format == "json") else "human"


def _emit(data: dict, fmt: str, human_renderer) -> None:
    if fmt == "json":
        click.echo(json_module.dumps(data, indent=2, sort_keys=True))
    else:
        human_renderer(data)


@click.group()
@click.version_option(version=__version__, prog_name="haltproof")
def cli():
    """HaltProof: emergency-shutdown orchestration and cryptographic audit-proof layer."""


@cli.command()
@click.argument("target_group")
@click.option("--nodes", help="Comma-separated explicit node list, overrides config group lookup.")
@click.option("--backend", "backend_name", help="Backend to use: kubernetes, slurm, or ipmi.")
@click.option("--confirm", is_flag=True, help="Actually execute the halt. Without this, dry-run only.")
@click.option("--reason", default="haltproof halt requested", help="Reason recorded for drain operations.")
@click.option("--operator-id", help="Operator identity to record. Defaults to OS user.")
@click.option("--config", "config_path", help="Path to a haltproof.toml config file.")
@click.option("--attestation-log", "attestation_log_path", help="Path to the attestation log file.")
@click.option(
    "--attestation-key",
    "attestation_key_path",
    help="Path to the Ed25519 private key used to sign the attestation.",
)
@click.option("--no-sign", is_flag=True, help="Skip signing (not recommended); still logs the record unsigned.")
@click.option("--remote-collector", "remote_collector_url", help="Optional URL to POST the signed attestation to.")
@_format_option
def halt(
    target_group,
    nodes,
    backend_name,
    confirm,
    reason,
    operator_id,
    config_path,
    attestation_log_path,
    attestation_key_path,
    no_sign,
    remote_collector_url,
    output_format,
    json_flag,
):
    """Drain, isolate, and power-fence TARGET_GROUP.

    Dry-run is the default: nothing destructive runs without --confirm.
    """
    fmt = _resolve_format(output_format, json_flag)
    node_list = [n.strip() for n in nodes.split(",")] if nodes else None

    try:
        result = core.run_halt(
            target_group=target_group,
            nodes=node_list,
            backend_name=backend_name,
            confirm=confirm,
            reason=reason,
            operator_id=operator_id,
            config_path=config_path,
            attestation_log_path=attestation_log_path,
            attestation_key_path=attestation_key_path,
            no_sign=no_sign,
            remote_collector_url=remote_collector_url,
        )
    except core.HaltProofError as exc:
        raise click.ClickException(str(exc)) from exc

    def render(data: dict) -> None:
        mode = "DRY-RUN" if data["dry_run"] else "EXECUTED"
        click.echo(f"HaltProof halt [{mode}] target-group={data['target_group']} backend={data['backend']}")
        click.echo(f"  attestation id={data['id']} seq={data['seq']} signed={data['signed']}")
        click.echo(f"  operator={data['operator']} nodes={', '.join(data['nodes'])}")
        for step in data["steps"]:
            cmd = " ".join(step["command"]) if step["command"] else "(no command)"
            click.echo(f"  [{step['status'].upper():8s}] {step['node']:20s} {step['operation']:16s} {cmd}")
        click.echo(f"  summary: {data['summary']}")
        click.echo(f"  attestation log: {data['attestation_log_path']}")

    _emit(result, fmt, render)

    if result.get("any_failures"):
        sys.exit(1)


@cli.command()
@click.argument("attestation_ref")
@click.option(
    "--attestation-log",
    "attestation_log_path",
    help="Path to the attestation log to search when ATTESTATION_REF is an id or sequence number.",
)
@click.option(
    "--trusted-key",
    "trusted_key_path",
    help="Path to a trusted Ed25519 public key; if given, the record's signing key must match it.",
)
@_format_option
def verify(attestation_ref, attestation_log_path, trusted_key_path, output_format, json_flag):
    """Verify the signature of an attestation record and print its timeline.

    ATTESTATION_REF is either a path to a file containing the record, or an
    attestation id / sequence number to look up in the attestation log.
    """
    fmt = _resolve_format(output_format, json_flag)

    try:
        result = core.run_verify(
            attestation_ref=attestation_ref,
            attestation_log_path=attestation_log_path,
            trusted_key_path=trusted_key_path,
        )
    except core.HaltProofError as exc:
        raise click.ClickException(str(exc)) from exc

    def render(data: dict) -> None:
        rec = data["record"]
        status_line = "VALID SIGNATURE" if data["valid"] else f"INVALID SIGNATURE ({data['error']})"
        click.echo(f"Attestation {rec['id']} (seq {rec['seq']}): {status_line}")
        click.echo(f"  action={rec['action']} target_group={rec['target_group']} backend={rec['backend']}")
        click.echo(f"  operator={rec['operator']} hostname={rec['hostname']} timestamp={rec['timestamp']}")
        click.echo(f"  dry_run={rec['dry_run']} confirmed={rec['confirmed']}")
        click.echo("  timeline:")
        for step in rec["steps"]:
            cmd = " ".join(step["command"]) if step["command"] else "(no command)"
            click.echo(
                f"    {step['timestamp']}  [{step['status'].upper():8s}] "
                f"{step['node']:20s} {step['operation']:16s} {cmd}"
            )
        click.echo(f"  summary: {rec['summary']}")

    _emit(result, fmt, render)

    if not result["valid"]:
        sys.exit(1)


@cli.command()
@click.option("--backend", "backend_name", help="Backend to check status for; defaults to auto-detected/configured backend.")
@click.option("--nodes", help="Comma-separated node list to report health for.")
@click.option("--group", "target_group", help="Named target group (from config) to report health for.")
@click.option("--config", "config_path", help="Path to a haltproof.toml config file.")
@_format_option
def status(backend_name, nodes, target_group, config_path, output_format, json_flag):
    """Show backend auto-detection results and optional target-group health."""
    fmt = _resolve_format(output_format, json_flag)
    node_list = [n.strip() for n in nodes.split(",")] if nodes else None

    try:
        result = core.run_status(
            backend_name=backend_name,
            nodes=node_list,
            target_group=target_group,
            config_path=config_path,
        )
    except core.HaltProofError as exc:
        raise click.ClickException(str(exc)) from exc

    def render(data: dict) -> None:
        click.echo("Backend availability:")
        for name, present in data["available_backends"].items():
            click.echo(f"  {name:12s} {'available' if present else 'not found'}")
        click.echo(f"Auto-detected backend: {data['auto_detected_backend'] or 'none'}")
        if data["nodes"]:
            click.echo(f"Node status ({data['active_backend']}):")
            for node in data["nodes"]:
                reach = "reachable" if node["reachable"] else "unreachable"
                click.echo(f"  {node['node']:20s} {node['state']:12s} {reach}")

    _emit(result, fmt, render)


@cli.command()
@click.option("--output", "output_path", help="Path to write the private key to.")
@click.option("--force", is_flag=True, help="Overwrite an existing key at the output path.")
@_format_option
def keygen(output_path, force, output_format, json_flag):
    """Generate an Ed25519 keypair for attestation signing.

    The private key is written with 0600 permissions and is never printed
    or logged. Anyone holding it can forge attestation records that verify
    as signed by you, so treat it like an SSH private key: keep it off
    shared filesystems, back it up somewhere access-controlled, and rotate
    it if you suspect it was exposed.
    """
    fmt = _resolve_format(output_format, json_flag)

    try:
        result = core.run_keygen(output_path=output_path, force=force)
    except core.HaltProofError as exc:
        raise click.ClickException(str(exc)) from exc

    def render(data: dict) -> None:
        click.echo("Ed25519 keypair generated.")
        click.echo(f"  private key: {data['private_key_path']} (permissions {data['private_key_permissions']})")
        click.echo(f"  public key:  {data['public_key_path']}")
        click.echo(
            "  keep the private key secret and back it up securely; "
            "anyone holding it can forge attestation records signed as you."
        )

    _emit(result, fmt, render)


@cli.command("mcp-server")
def mcp_server_command():
    """Start the HaltProof MCP server on stdio."""
    from haltproof.mcp_server import run_server

    run_server()


def main():
    cli()


if __name__ == "__main__":
    main()
