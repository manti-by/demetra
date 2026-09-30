from typing import Any

import demetra.services.clickup as service
from demetra.library.exceptions import ClickUpConfigError, ClickUpError, EnvironmentConfigError
from demetra.library.models import Context, SessionEnvironment


def _ticket_from_task(task: dict) -> dict[str, Any]:
    """Return the ticket summary dict for a created or updated task payload.

    Args:
        task: The ClickUp task payload.

    Returns:
        dict[str, Any]: The ticket id, identifier and title.
    """
    return {
        "ticket_id": task["id"],
        "identifier": task.get("custom_id") or task["id"],
        "title": task.get("name", ""),
    }


async def update_ticket_status(task_id: str, state_id: str) -> bool:
    """Move a ClickUp task to a given status.

    Args:
        task_id: The ClickUp task id.
        state_id: The target status label (ClickUp statuses are names, not ids).

    Returns:
        bool: True when the update succeeded.
    """
    result = await service.clickup_request(method="PUT", path=f"/task/{task_id}", json={"status": state_id})
    status = result.get("status") or {}
    if not isinstance(status, dict):
        return False
    return bool(result.get("id")) and str(status.get("status", "")).casefold() == state_id.casefold()


async def post_comment(task_id: str, body: str) -> bool:
    """Post a comment on a ClickUp task.

    Args:
        task_id: The ClickUp task id.
        body: The comment body markdown.

    Returns:
        bool: True when the comment was created successfully.
    """
    result = await service.clickup_request(
        method="POST",
        path=f"/task/{task_id}/comment",
        json={"comment_text": body, "notify_all": False},
    )
    return bool(result.get("id"))


async def clickup_cleanup(context: Context, is_success: bool) -> None:
    """Move the task to In Review on success, or back to TODO on failure.

    Args:
        context: The workflow context with the tracker task.
        is_success: Whether the workflow completed successfully.

    Raises:
        ClickUpError: When the target status is not configured.
    """
    if is_success:
        service.print_message("Workflow complete", style="heading")
        try:
            state = context.environment.clickup_state("in_review")
        except EnvironmentConfigError as e:
            raise ClickUpError("ClickUp state 'in_review' is not configured") from e
        await service.update_ticket_status(task_id=context.linear_task.id, state_id=state)
        return

    service.print_message("Moving back a ticket in TODO column", style="heading")
    try:
        state = context.environment.clickup_state("todo")
    except EnvironmentConfigError as e:
        raise ClickUpError("ClickUp state 'todo' is not configured") from e
    await service.update_ticket_status(task_id=context.linear_task.id, state_id=state)


async def create_clickup_ticket(
    title: str,
    description: str,
    technical_requirements: str,
    acceptance_criteria: str,
    list_id: str | None = None,
    state: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Create a new ClickUp task from structured ticket fields.

    Composes the description sections, applies defaults from the user-shared
    environment or settings for the target list and status, and returns the
    created task.

    Args:
        title: The task name.
        description: The task description body.
        technical_requirements: Technical requirements section content.
        acceptance_criteria: Acceptance criteria section content.
        list_id: Optional target list id; defaults to ``CLICKUP_LIST_ID``.
        state: Optional initial status; defaults to ``CLICKUP_DEFAULT_STATE``.
        user_id: Optional user id whose shared env overrides the defaults.

    Returns:
        dict[str, Any]: The created task with its id, identifier and title.

    Raises:
        ClickUpConfigError: When the list id or default status is missing.
        ClickUpError: When the API rejects the task.
    """
    full_description = (
        f"### Description\n{description}\n\n"
        f"### Tech Requirements\n{technical_requirements}\n\n"
        f"### Acceptance Criteria\n{acceptance_criteria}"
    )

    user_environment = await service.get_user_environments_decrypted(user_id=user_id) if user_id else {}
    environment = SessionEnvironment(project_environment={}, user_environment=user_environment)

    try:
        resolved_list_id = list_id or environment.clickup_value("list_id")
    except EnvironmentConfigError as e:
        raise ClickUpConfigError("ClickUp list id is not configured") from e
    try:
        resolved_state = state or environment.clickup_value("default_state")
    except EnvironmentConfigError as e:
        raise ClickUpConfigError("ClickUp default state is not configured") from e

    result = await service.clickup_request(
        method="POST",
        path=f"/list/{resolved_list_id}/task",
        json={
            "name": title,
            "markdown_content": full_description,
            "status": resolved_state,
            "priority": 3,
            "tags": [service.CLICKUP["feature_tag"]],
        },
    )
    if not result.get("id"):
        raise ClickUpError("ClickUp API returned no task data")
    return _ticket_from_task(result)


async def _find_existing_research_ticket(list_id: str, title: str) -> dict[str, Any] | None:
    """Return an existing task with the given name in the list, if any.

    The ClickUp API has no exact-name filter, so the list is paged through
    and matched client-side. Retrying task creation after a lost response
    would otherwise create duplicates.

    Args:
        list_id: The ClickUp list id to search.
        title: The exact task name to match.

    Returns:
        dict[str, Any] | None: The matching task summary, or None.
    """
    for page in range(service.TASKS_PAGE_LIMIT):
        payload = await service.clickup_request(
            method="GET",
            path=f"/list/{list_id}/task",
            params=[("include_closed", "true"), ("subtasks", "true"), ("page", page)],
        )
        tasks = payload.get("tasks") or []
        for task in tasks:
            if task.get("name") == title:
                return _ticket_from_task(task)
        if payload.get("last_page", True) or not tasks:
            break
    return None


async def create_research_ticket(context: Context, report: str, *, title: str | None = None) -> dict[str, Any]:
    """Create a related ClickUp task holding a research report.

    Mirrors the originating task: the new task is created in the same list
    and priority, in the ``prd`` status, and tagged with the feature tag plus
    the backend/frontend tags carried by the source task. The report is used
    verbatim as the markdown description.

    Idempotent per source task: a task with the deterministic name is looked
    up first and its description refreshed instead of creating a duplicate.

    Args:
        context: The workflow context with the originating task.
        report: The research report markdown, used as the description.
        title: Optional task name; defaults to
            ``Research: <source identifier> — <source title>``.

    Returns:
        dict[str, Any]: The created (or existing) task summary.

    Raises:
        ClickUpConfigError: When the source list or the PRD status is
            missing (permanent configuration error).
        ClickUpError: When the API request fails (transient, retryable).
    """
    list_id = context.linear_task.linear_project_id
    if not list_id:
        raise ClickUpConfigError("Source ClickUp task has no list to attach the research task to")

    try:
        state = context.environment.clickup_state("prd")
    except EnvironmentConfigError as e:
        raise ClickUpConfigError("ClickUp state 'prd' is not configured") from e

    resolved_title = title or f"Research: {context.linear_task.identifier} — {context.linear_task.title}"
    existing = await _find_existing_research_ticket(list_id=list_id, title=resolved_title)
    if existing is not None:
        updated = await service.clickup_request(
            method="PUT",
            path=f"/task/{existing['ticket_id']}",
            json={"markdown_content": report},
        )
        if not updated.get("id"):
            raise ClickUpError("Failed to update research task description")
        return _ticket_from_task(updated)

    tags = [service.CLICKUP["feature_tag"]]
    source_labels = {label.casefold() for label in context.linear_task.labels}
    if "backend" in source_labels and service.CLICKUP["backend_tag"]:
        tags.append(service.CLICKUP["backend_tag"])
    if "frontend" in source_labels and service.CLICKUP["frontend_tag"]:
        tags.append(service.CLICKUP["frontend_tag"])

    task_input: dict[str, Any] = {
        "name": resolved_title,
        "markdown_content": report,
        "status": state,
        "tags": tags,
    }
    if context.linear_task.priority:
        task_input["priority"] = context.linear_task.priority

    result = await service.clickup_request(method="POST", path=f"/list/{list_id}/task", json=task_input)
    if not result.get("id"):
        raise ClickUpError("Failed to create research ClickUp task")
    return _ticket_from_task(result)
