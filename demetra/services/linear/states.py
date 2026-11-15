import logging
import time
from dataclasses import dataclass

import demetra.services.linear as service
from demetra.library.exceptions import LinearError


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LinearState:
    """A workflow state (a board column) of a Linear team.

    Attributes:
        id: The Linear state id.
        name: The column label, e.g. ``"Awaiting Input"``.
        type: The Linear state type, e.g. ``"started"``.
    """

    id: str
    name: str
    type: str


_TEAM_STATES_TTL = 300.0

_TEAM_STATES: dict[str, tuple[float, list[LinearState]]] = {}


def expected_state_label(name: str) -> str:
    """Return the Linear column label a workflow state name refers to.

    The name is the snake_case key demetra uses everywhere (``awaiting_input``),
    so the expected column is its title-cased form (``Awaiting Input``).

    Args:
        name: The workflow state name, e.g. ``"awaiting_input"``.

    Returns:
        str: The expected column label.
    """
    return " ".join(part for part in name.replace("-", "_").split("_") if part).title()


def _normalize(label: str) -> str:
    """Return the comparison form of a column label.

    Case, spacing and separator differences between the configured name and the
    Linear label are irrelevant, so only the alphanumeric characters are kept
    (``"In progress"`` and ``"in_progress"`` both become ``"inprogress"``).

    Args:
        label: The column label to normalize.

    Returns:
        str: The normalized label.
    """
    return "".join(character for character in label.casefold() if character.isalnum())


async def fetch_team_states(team_id: str) -> list[LinearState]:
    """Return the workflow states of a Linear team.

    The states are cached per team id for a bounded period, so a workflow run
    fetches them once no matter how many status transitions it makes, while a
    renamed column is still picked up without a process restart. A failed
    request is reported and yields an empty list so the caller falls back to the
    configured state ids instead of failing the workflow.

    Args:
        team_id: The Linear team id.

    Returns:
        list[LinearState]: The team's workflow states, empty when unavailable.
    """
    cached = _TEAM_STATES.get(team_id)
    if cached is not None and time.monotonic() - cached[0] < _TEAM_STATES_TTL:
        return cached[1]

    try:
        query = await service.get_query(name="get_team_states")
        result = await service.graphql_request(query=query, variables={"teamId": team_id})
    except (LinearError, OSError) as e:
        logger.warning(f"Failed to load the Linear workflow states of team {team_id}: {e}")
        return []

    team = (result.get("data") or {}).get("team") or {}
    states = [
        LinearState(id=state["id"], name=state.get("name") or "", type=state.get("type") or "")
        for state in (team.get("states") or {}).get("nodes") or []
        if state.get("id")
    ]
    if states:
        _TEAM_STATES[team_id] = (time.monotonic(), states)
    return states


async def resolve_state_id(*, name: str, configured_id: str, team_id: str | None) -> tuple[str | None, str | None]:
    """Resolve the Linear state id for a workflow state name.

    The team column named after the state wins over the configured
    ``LINEAR_STATE_<NAME>_ID``, so a stale or mis-pointed id can never park a
    ticket in a different column. The configured id is kept whenever the team
    has no column with that name, when the team id is unknown, and when the
    states cannot be loaded, so an intentional configuration is never
    overridden. ``awaiting_input`` is the exception: when the team has no
    *Awaiting Input* column, a configured id that is known to point at another
    column is rejected, so the ticket is left for manual recovery instead of
    being parked in, say, *Failed*.

    Args:
        name: The workflow state name, e.g. ``"awaiting_input"``.
        configured_id: The state id resolved from the environment layers.
        team_id: The Linear team id, or None when it is not configured.

    Returns:
        tuple[str | None, str | None]: The state id to use (None when the
            configured column is known to be the wrong one), and a warning
            describing a configuration mismatch (None when the configured id is
            correct).
    """
    if not team_id:
        return configured_id, None

    states = await fetch_team_states(team_id=team_id)
    if not states:
        return configured_id, None

    expected = _normalize(expected_state_label(name))
    matched = next((state for state in states if _normalize(state.name) == expected), None)
    configured = next((state for state in states if state.id == configured_id), None)
    if matched is None:
        if name == "awaiting_input" and configured is not None:
            return None, (
                f"Linear state '{name}' is configured as '{configured.name}', "
                f"but team {team_id} has no '{expected_state_label(name)}' column"
            )
        return configured_id, None
    if matched.id == configured_id:
        return configured_id, None

    if configured is None:
        warning = f"Linear state '{name}' is not a column of team {team_id}; using '{matched.name}' instead"
    else:
        warning = f"Linear state '{name}' is configured as '{configured.name}'; using '{matched.name}' instead"
    return matched.id, warning
