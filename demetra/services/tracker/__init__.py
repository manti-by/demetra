"""Issue-tracker facade dispatching on ``SessionEnvironment.issue_tracker``.

Mirrors ``demetra/services/agents/harness.py``: workflows, daemons and
``main.py`` import only this module, never ``services/linear`` or
``services/clickup`` directly, so a project or user can switch trackers via
the ``ISSUE_TRACKER`` environment key exactly like ``AGENT_HARNESS`` selects
the agent harness. Every function takes an optional ``environment``; when it
is omitted the tracker resolves from the user-shared env (when a ``user_id``
is given) and the ``settings.py`` default.
"""

from typing import Any

from demetra.library.models import Context, LinearTask, SessionEnvironment
from demetra.services import clickup as clickup_service
from demetra.services import linear as linear_service
from demetra.services.persistence.database import get_project_environments, get_user_environments_decrypted
from demetra.settings import CLICKUP, LINEAR


def resolve_environment(environment: SessionEnvironment | None) -> SessionEnvironment:
    """Return a usable environment, defaulting to bare settings when None.

    Args:
        environment: The caller-supplied environment, or None.

    Returns:
        SessionEnvironment: The environment to dispatch on.
    """
    if environment is not None:
        return environment
    return SessionEnvironment(project_environment={}, user_environment={})


async def load_environment(user_id: str | None, project_id: str | None = None) -> SessionEnvironment:
    """Build a resolver from the stored project and user-shared environments.

    Used by callers that only hold ids (the watcher daemon, task lookups by
    ``user_id``) and therefore cannot reuse ``Context.environment``.

    Args:
        user_id: The user id whose shared environment is consulted.
        project_id: Optional project id whose environment is consulted first.

    Returns:
        SessionEnvironment: The resolver over both layers plus settings.
    """
    user_environment = await get_user_environments_decrypted(user_id=user_id) if user_id else {}
    project_environment = await get_project_environments(project_id=project_id) if project_id else {}
    return SessionEnvironment(project_environment=project_environment, user_environment=user_environment)


def is_clickup(environment: SessionEnvironment | None) -> bool:
    """Return whether the resolved tracker is ClickUp.

    Args:
        environment: The caller-supplied environment, or None for settings.

    Returns:
        bool: True for ClickUp, False for Linear.
    """
    return resolve_environment(environment).issue_tracker == "clickup"


def research_labels(environment: SessionEnvironment | None = None) -> list[str]:
    """Return the labels that mark a ticket as a research task for the tracker.

    Args:
        environment: The caller-supplied environment, or None for settings.

    Returns:
        list[str]: The configured research labels (Linear labels or ClickUp
            tags).
    """
    if is_clickup(environment):
        return list(CLICKUP["research_labels"])
    return list(LINEAR["research_labels"])


async def get_todo_issues(
    project_name: str | None = None,
    *,
    user_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> list[LinearTask]:
    """Fetch TODO tickets from the active tracker.

    Args:
        project_name: Optional tracker project (Linear project / ClickUp
            list) name to filter on.
        user_id: Optional user id whose shared env selects the tracker and
            overrides its config.
        environment: Optional resolved environment; built from ``user_id``
            when omitted.

    Returns:
        list[LinearTask]: The matching TODO tickets.
    """
    if environment is None:
        environment = await load_environment(user_id=user_id)
    if is_clickup(environment):
        return await clickup_service.get_todo_issues(
            project_name=project_name, user_id=user_id, environment=environment
        )
    return await linear_service.get_todo_issues(project_name=project_name, user_id=user_id, environment=environment)


async def get_task_by_id(task_id: str, environment: SessionEnvironment | None = None) -> LinearTask | None:
    """Fetch a single ticket by id from the active tracker.

    Args:
        task_id: The tracker ticket id.
        environment: Optional resolved environment selecting the tracker.

    Returns:
        LinearTask | None: The ticket, or None when it does not exist.
    """
    if is_clickup(environment):
        return await clickup_service.get_clickup_task_by_id(task_id=task_id)
    return await linear_service.get_linear_task_by_id(task_id=task_id)


async def get_task(
    project_name: str,
    *,
    user_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> LinearTask | None:
    """Return the highest-priority TODO ticket for a project from the active tracker.

    Args:
        project_name: The tracker project (Linear project / ClickUp list) name.
        user_id: Optional user id whose shared env selects the tracker.
        environment: Optional resolved environment; built from ``user_id``
            when omitted.

    Returns:
        LinearTask | None: The selected ticket, or None when there are none.
    """
    if environment is None:
        environment = await load_environment(user_id=user_id)
    if is_clickup(environment):
        return await clickup_service.get_clickup_task(
            project_name=project_name, user_id=user_id, environment=environment
        )
    return await linear_service.get_linear_task(project_name=project_name, user_id=user_id, environment=environment)


async def update_ticket_status(task_id: str, state_id: str, environment: SessionEnvironment | None = None) -> bool:
    """Move a ticket to a state on the active tracker.

    Args:
        task_id: The tracker ticket id.
        state_id: The tracker state, resolved via
            :meth:`SessionEnvironment.tracker_state` (a Linear state id or a
            ClickUp status label).
        environment: Optional resolved environment selecting the tracker.

    Returns:
        bool: True when the update succeeded.
    """
    if is_clickup(environment):
        return await clickup_service.update_ticket_status(task_id=task_id, state_id=state_id)
    return await linear_service.update_ticket_status(task_id=task_id, state_id=state_id)


async def post_comment(task_id: str, body: str, environment: SessionEnvironment | None = None) -> bool:
    """Post a comment on a ticket on the active tracker.

    Args:
        task_id: The tracker ticket id.
        body: The comment body markdown.
        environment: Optional resolved environment selecting the tracker.

    Returns:
        bool: True when the comment was created successfully.
    """
    if is_clickup(environment):
        return await clickup_service.post_comment(task_id=task_id, body=body)
    return await linear_service.post_comment(task_id=task_id, body=body)


async def create_ticket(
    title: str,
    description: str,
    technical_requirements: str,
    acceptance_criteria: str,
    *,
    user_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> dict[str, Any]:
    """Create a ticket from structured fields on the active tracker.

    Args:
        title: The ticket title.
        description: The ticket description body.
        technical_requirements: Technical requirements section content.
        acceptance_criteria: Acceptance criteria section content.
        user_id: Optional user id whose shared env selects the tracker and
            supplies the default team/list and state.
        environment: Optional resolved environment; built from ``user_id``
            when omitted.

    Returns:
        dict[str, Any]: The created ticket with its id, identifier and title.
    """
    if environment is None:
        environment = await load_environment(user_id=user_id)
    if is_clickup(environment):
        return await clickup_service.create_clickup_ticket(
            title=title,
            description=description,
            technical_requirements=technical_requirements,
            acceptance_criteria=acceptance_criteria,
            user_id=user_id,
        )
    return await linear_service.create_linear_ticket(
        title=title,
        description=description,
        technical_requirements=technical_requirements,
        acceptance_criteria=acceptance_criteria,
        user_id=user_id,
    )


async def create_research_ticket(context: Context, report: str, *, title: str | None = None) -> dict[str, Any]:
    """Create the related research ticket on the tracker of the context.

    Args:
        context: The workflow context with the originating ticket.
        report: The research report markdown, used as the description.
        title: Optional ticket title override.

    Returns:
        dict[str, Any]: The created (or existing) ticket summary.
    """
    if is_clickup(context.environment):
        return await clickup_service.create_research_ticket(context=context, report=report, title=title)
    return await linear_service.create_research_ticket(context=context, report=report, title=title)


async def tracker_cleanup(context: Context, is_success: bool) -> None:
    """Move the ticket to In Review on success, or back to TODO on failure.

    Args:
        context: The workflow context with the ticket.
        is_success: Whether the workflow completed successfully.
    """
    if is_clickup(context.environment):
        await clickup_service.clickup_cleanup(context=context, is_success=is_success)
        return
    await linear_service.linear_cleanup(context=context, is_success=is_success)


__all__ = [
    "create_research_ticket",
    "create_ticket",
    "get_task",
    "get_task_by_id",
    "get_todo_issues",
    "is_clickup",
    "load_environment",
    "post_comment",
    "research_labels",
    "resolve_environment",
    "tracker_cleanup",
    "update_ticket_status",
]
