"""Shared state and Compose helpers for the deploy daemon and the worker swap."""

import json
import logging
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from demetra.library.models import DeployState
from demetra.settings import DEPLOY


logger = logging.getLogger(__name__)


def default_state_path() -> Path:
    """Resolve the deploy state file path.

    The default lives in the deployer's own volume, never in the app home
    volume: the daemon runs as root, so a state directory created there would
    be root-owned and would block the ``demetra`` user's own ``~/.demetra``
    tree (worktrees, venvs) in the shared ``demetra_app_data`` volume.

    Returns:
        Path: The configured path, defaulting to the deployer state volume.
    """
    if state_path := DEPLOY["state_path"]:
        return state_path
    return Path("/var/lib/demetra/deployer-state.json")


def load_state(path: Path) -> DeployState:
    """Load the persisted deploy state.

    A missing file is a fresh daemon; an unreadable file or a decoded value that
    is not a JSON object is logged and treated as an empty state so a corrupt
    state never stops the daemon. A ``null`` or list payload would otherwise
    escape the recovery handler as an ``AttributeError`` on every poll.

    Args:
        path: The JSON state file path.

    Returns:
        DeployState: The persisted state, or an empty state.
    """
    if not path.exists():
        return DeployState()
    try:
        payload = json.loads(path.read_text())
    except (OSError, TypeError, ValueError):
        logger.exception(f"Failed to read the deploy state from {path}")
        return DeployState()
    if not isinstance(payload, dict):
        logger.error(f"Ignoring the deploy state in {path}: the payload is not a JSON object")
        return DeployState()
    return DeployState.from_payload(payload=payload)


def save_state(path: Path, state: DeployState) -> None:
    """Persist the deploy state atomically, logging instead of failing the cycle.

    The state file is load-bearing: it holds the live worker generation and the
    ids already signalled for draining. Writing it in place could leave a
    truncated file after a crash or a full disk, which would reset the state and
    make a later swap retire the live generation. A unique temp file in the
    same directory is renamed over the target only once it is complete.

    Args:
        path: The JSON state file path.
        state: The state to write.
    """
    temp_path = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(asdict(state), indent=2))
        temp_path.replace(path)
    except OSError:
        logger.exception(f"Failed to write the deploy state to {path}")
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            logger.exception(f"Failed to remove the temporary state file {temp_path}")


def compose_command(checkout_path: Path) -> list[str]:
    """Build a ``docker compose`` prefix pinned to the host checkout.

    Args:
        checkout_path: The host checkout that holds the compose file and env.

    Returns:
        list[str]: The ``docker compose`` command prefix.
    """
    checkout = str(checkout_path)
    return [
        str(DEPLOY["docker_path"]),
        "compose",
        "--project-directory",
        checkout,
        "--env-file",
        str(checkout_path / ".env.docker"),
    ]
