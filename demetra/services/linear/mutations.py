from typing import Any

import demetra.services.linear as service
from demetra.library.exceptions import LinearConfigError, LinearError
from demetra.library.models import Context


async def update_ticket_status(task_id: str, state_id: str) -> bool:
    """Move a Linear issue to a given state.

    Args:
        task_id: The Linear issue id.
        state_id: The target Linear state id.

    Returns:
        bool: True when the update succeeded.
    """
    query = await service.get_query(name="update_issue_status")
    result = await service.graphql_request(query=query, variables={"issueId": task_id, "stateId": state_id})
    if result is None:
        return False
    data = result.get("data")
    if data is None:
        return False
    return data.get("issueUpdate", {}).get("success", False)


async def post_comment(task_id: str, body: str) -> bool:
    """Post a comment on a Linear issue.

    Args:
        task_id: The Linear issue id.
        body: The comment body markdown.

    Returns:
        bool: True when the comment was created successfully.
    """
    query = await service.get_query(name="create_issue_comment")
    result = await service.graphql_request(query=query, variables={"issueId": task_id, "body": body})
    if result is None:
        return False
    data = result.get("data")
    if data is None:
        return False
    return data.get("commentCreate", {}).get("success", False)


async def linear_cleanup(context: Context, is_success: bool):
    """Move the task to In Review on success, or back to TODO on failure.

    Args:
        context: The workflow context with the Linear task.
        is_success: Whether the workflow completed successfully.
    """
    if is_success:
        service.print_message("Workflow complete", style="heading")
        state_id = await service.get_linear_config_value(name="in_review", user_id=context.project.user_id)
        if state_id is None:
            raise LinearError("Linear state 'in_review' is not configured")
        await service.update_ticket_status(task_id=context.linear_task.id, state_id=state_id)
        return

    service.print_message("Moving back a ticket in TODO column", style="heading")
    state_id = await service.get_linear_config_value(name="todo", user_id=context.project.user_id)
    if state_id is None:
        raise LinearError("Linear state 'todo' is not configured")
    await service.update_ticket_status(task_id=context.linear_task.id, state_id=state_id)


async def create_linear_ticket(
    title: str,
    description: str,
    technical_requirements: str,
    acceptance_criteria: str,
    team_id: str | None = None,
    state_id: str | None = None,
    project_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Create a new Linear issue from structured ticket fields.

    Composes the description sections, applies defaults from the user-shared
    environment or settings for any missing ids, and returns the created issue.

    Args:
        title: The issue title.
        description: The issue description body.
        technical_requirements: Technical requirements section content.
        acceptance_criteria: Acceptance criteria section content.
        team_id: Optional team id; defaults to the configured team.
        state_id: Optional initial state id; defaults to the configured state.
        project_id: Optional project id to attach the issue to.
        user_id: Optional user id whose shared env overrides the defaults.

    Returns:
        dict[str, Any]: The created issue with its id, identifier and title.

    Raises:
        LinearError: When the ticket creation fails or returns no issue.
    """
    full_description = (
        f"### Description\n{description}\n\n"
        f"### Tech Requirements\n{technical_requirements}\n\n"
        f"### Acceptance Criteria\n{acceptance_criteria}"
    )

    query = await service.get_query(name="create_issue")
    variables = {
        "input": {
            "title": title,
            "description": full_description,
            "teamId": team_id or await service.get_linear_config_value(name="team_id", user_id=user_id),
            "stateId": state_id or await service.get_linear_config_value(name="default_state", user_id=user_id),
            "projectId": project_id,
            "labelIds": [service.LINEAR["feature_label_id"]],
            "createAsUser": "Demetra",
            "priority": 3,
        }
    }
    result = await service.graphql_request(query=query, variables=variables)

    if not result.get("data", {}).get("issueCreate", {}).get("success"):
        raise LinearError("Failed to create Linear ticket")

    issue = result.get("data", {}).get("issueCreate", {}).get("issue")
    if not issue:
        raise LinearError("Linear API returned success but no issue data")

    return {
        "ticket_id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
    }


async def _find_existing_research_ticket(linear_project_id: str, title: str) -> dict[str, Any] | None:
    """Return an existing issue with the given title in the project, if any.

    Retrying ``issueCreate`` after a post-commit transport failure would
    otherwise create duplicates; the deterministic research title lets the
    creation step look up the issue it may already have created.

    Args:
        linear_project_id: The Linear project id to search.
        title: The exact issue title to match.

    Returns:
        dict[str, Any] | None: The matching issue with its id, identifier and
            title, or None when no issue matches.
    """
    query = await service.get_query(name="get_issue_by_title")
    result = await service.graphql_request(
        query=query,
        variables={"projectId": linear_project_id, "title": title},
    )
    data = (result or {}).get("data") or {}
    issues = (data.get("issues") or {}).get("nodes") or []
    if not issues:
        return None

    issue = issues[0]
    return {
        "ticket_id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
    }


async def create_research_ticket(context: Context, report: str, *, title: str | None = None) -> dict[str, Any]:
    """Create a related Linear issue holding a research report.

    Mirrors the originating ticket: the issue is created in the same Linear
    project and priority, in the ``prd`` state, and labelled with the feature
    label plus the backend/frontend labels carried by the source ticket. The
    report is used verbatim as the issue description.

    Idempotent per source ticket: an issue with the deterministic title is
    looked up first and reused, so retrying after a lost ``issueCreate``
    response does not create a duplicate.

    Args:
        context: The workflow context with the originating Linear task.
        report: The research report markdown, used as the description.
        title: Optional issue title; defaults to
            ``Research: <source identifier> — <source title>``.

    Returns:
        dict[str, Any]: The created (or existing) issue with its id,
            identifier and title.

    Raises:
        LinearConfigError: When the source project, the PRD state or the team id
            is missing, or when Linear rejects the request (permanent).
        LinearError: When the API request fails (transient, e.g. network).
    """
    linear_project_id = context.linear_task.linear_project_id
    if not linear_project_id:
        raise LinearConfigError("Source Linear task has no project to attach the research ticket to")

    state_id = await service.get_linear_config_value(name="prd", user_id=context.project.user_id)
    if state_id is None:
        raise LinearConfigError("Linear state 'prd' is not configured")

    team_id = await service.get_linear_config_value(name="team_id", user_id=context.project.user_id)
    if team_id is None:
        raise LinearConfigError("Linear team id is not configured")

    resolved_title = title or f"Research: {context.linear_task.identifier} — {context.linear_task.title}"
    existing = await _find_existing_research_ticket(linear_project_id=linear_project_id, title=resolved_title)
    if existing is not None:
        return existing

    label_ids = [service.LINEAR["feature_label_id"]]
    source_labels = {label.casefold() for label in context.linear_task.labels}
    if "backend" in source_labels and service.LINEAR["backend_label_id"]:
        label_ids.append(service.LINEAR["backend_label_id"])
    if "frontend" in source_labels and service.LINEAR["frontend_label_id"]:
        label_ids.append(service.LINEAR["frontend_label_id"])

    ticket_input: dict[str, Any] = {
        "title": resolved_title,
        "description": report,
        "teamId": team_id,
        "stateId": state_id,
        "projectId": linear_project_id,
        "labelIds": label_ids,
        "createAsUser": "Demetra",
    }
    if context.linear_task.priority is not None:
        ticket_input["priority"] = context.linear_task.priority

    query = await service.get_query(name="create_issue")
    result = await service.graphql_request(query=query, variables={"input": ticket_input})

    data = (result or {}).get("data") or {}
    issue_create = data.get("issueCreate") or {}
    if not issue_create.get("success"):
        errors = (result or {}).get("errors")
        detail = f": {errors}" if errors else ""
        raise LinearConfigError(f"Failed to create research Linear ticket{detail}")

    issue = issue_create.get("issue")
    if not issue:
        raise LinearConfigError("Linear API returned success but no issue data")

    return {
        "ticket_id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
    }
