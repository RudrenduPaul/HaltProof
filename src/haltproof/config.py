"""Configuration file loading for HaltProof.

Config is optional. Every setting it can provide also has a CLI flag, and
an explicit CLI flag always overrides the config file. Config is read from
(in order): a path given by ``--config``/``HALTPROOF_CONFIG``, then
``./haltproof.toml``, then ``~/.config/haltproof/config.toml``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python < 3.11
    import tomli as tomllib

DEFAULT_LOCATIONS = [
    Path("haltproof.toml"),
    Path.home() / ".config" / "haltproof" / "config.toml",
]


class HaltProofConfig:
    """Thin wrapper over the parsed TOML config with defaulted lookups."""

    def __init__(self, data: dict[str, Any] | None = None, source: Path | None = None):
        self.data = data or {}
        self.source = source

    @property
    def backend(self) -> str | None:
        return self.data.get("backend")

    @property
    def operator_id(self) -> str | None:
        return self.data.get("operator_id")

    @property
    def attestation_log_path(self) -> str | None:
        return self.data.get("attestation_log_path")

    @property
    def attestation_key_path(self) -> str | None:
        return self.data.get("attestation_key_path")

    @property
    def remote_collector_url(self) -> str | None:
        return self.data.get("remote_collector_url")

    @property
    def namespace(self) -> str:
        return self.data.get("kubernetes", {}).get("namespace", "default")

    @property
    def ipmi_user(self) -> str | None:
        return self.data.get("ipmi", {}).get("user")

    def resolve_group(self, group: str) -> list[str] | None:
        """Look up a named target group's node list, if defined."""
        groups = self.data.get("groups", {})
        nodes = groups.get(group)
        if nodes is None:
            return None
        return list(nodes)


def load_config(explicit_path: str | None = None) -> HaltProofConfig:
    """Load config from the first location that exists."""
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    env_path = os.environ.get("HALTPROOF_CONFIG")
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(DEFAULT_LOCATIONS)

    for candidate in candidates:
        if candidate.exists():
            with candidate.open("rb") as fh:
                data = tomllib.load(fh)
            return HaltProofConfig(data=data, source=candidate)

    return HaltProofConfig()
