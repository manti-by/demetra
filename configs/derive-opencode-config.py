"""Derive a provider-credentials-only OpenCode config from a host config file.

The host credential file mounted into the containers carries model provider
credentials, but it is also an OpenCode config that may hold MCP servers,
agents, plugins or permissions. Mounting it directly as the container's global
``opencode.json`` would let those host sections shadow the project config, so
the container derives a config that keeps only ``$schema`` and ``provider``.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any


PROVIDER_ONLY_KEYS = ("$schema", "provider")


def derive_config(source: Path) -> dict[str, Any]:
    """Return the provider-credentials-only subset of a host OpenCode config.

    Args:
        source: Path to the host OpenCode config JSON file.

    Returns:
        dict[str, Any]: A config holding only ``$schema`` and ``provider``.

    Raises:
        ValueError: When the file is not a JSON object or ``provider`` is not
            an object.
    """
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{source} must contain a JSON object")
    if "provider" in data and not isinstance(data["provider"], dict):
        raise ValueError(f"{source} has a non-object 'provider' section")

    return {key: data[key] for key in PROVIDER_ONLY_KEYS if key in data}


def write_config(config: dict[str, Any], target: Path) -> None:
    """Write a derived config atomically with owner-only permissions.

    The temporary file is created with mode ``0600`` before any credential is
    written, so provider keys are never readable by another user during the
    write. A failed write or replace removes the temporary file.

    Args:
        config: The derived config mapping.
        target: The destination path.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    payload = json.dumps(config, indent=2) + "\n"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        temporary.replace(target)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    """Derive the container's global OpenCode config from the mounted host file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Host OpenCode config with provider credentials")
    parser.add_argument("target", type=Path, help="Derived provider-only config path")
    args = parser.parse_args()

    write_config(config=derive_config(source=args.source), target=args.target)


if __name__ == "__main__":
    main()
