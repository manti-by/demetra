from typing import Any

import demetra.services.linear as service
from demetra.library.exceptions import EnvironmentConfigError, LinearConfigError, LinearError
from demetra.library.models import Context, SessionEnvironment


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
        try:
            state_id = context.environment.linear_state("in_review")
        except EnvironmentConfigError as e:
            raise LinearError("Linear state 'in_review' is not configured") from e
        await service.update_ticket_status(task_id=context.linear_task.id, state_id=state_id)
        return

    service.print_message("Moving back a ticket in TODO column", style="heading")
    try:
        state_id = context.environment.linear_state("todo")
    except EnvironmentConfigError as e:
        raise LinearError("Linear state 'todo' is not configured") from e
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

    user_environment = await service.get_user_environments_decrypted(user_id=user_id) if user_id else {}
    environment = SessionEnvironment(project_environment={}, user_environment=user_environment)

    try:
        resolved_team_id = team_id or environment.linear_value("team_id")
    except EnvironmentConfigError as e:
        raise LinearError("Linear team id is not configured") from e
    try:
        resolved_state_id = state_id or environment.linear_value("default_state")
    except EnvironmentConfigError as e:
        raise LinearError("Linear state 'default_state' is not configured") from e

    query = await service.get_query(name="create_issue")
    variables = {
        "input": {
            "title": title,
            "description": full_description,
            "teamId": resolved_team_id,
            "stateId": resolved_state_id,
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

    Raises:
        LinearError: When the lookup request fails or returns GraphQL errors.
    """
    query = await service.get_query(name="get_issue_by_title")
    result = await service.graphql_request(
        query=query,
        variables={"projectId": linear_project_id, "title": title},
    )
    if result is None:
        raise LinearError("Failed to lookup existing research ticket: empty response")
    if result.get("errors"):
        raise LinearError(f"Failed to lookup existing research ticket: {result['errors']}")
    data = result.get("data")
    if data is None:
        raise LinearError("Failed to lookup existing research ticket: missing data")
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
    looked up first and reused (updating its description so a retried research
    run does not leave a stale report), so retrying after a lost
    ``issueCreate`` response does not create a duplicate.

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
            is missing (permanent configuration error).
        LinearError: When the API request fails or Linear rejects the
            creation/update (transient, retryable).
    """
    linear_project_id = context.linear_task.linear_project_id
    if not linear_project_id:
        raise LinearConfigError("Source Linear task has no project to attach the research ticket to")

    try:
        state_id = context.environment.linear_state("prd")
    except EnvironmentConfigError as e:
        raise LinearConfigError("Linear state 'prd' is not configured") from e

    try:
        team_id = context.environment.linear_value("team_id")
    except EnvironmentConfigError as e:
        raise LinearConfigError("Linear team id is not configured") from e

    resolved_title = title or f"Research: {context.linear_task.identifier} — {context.linear_task.title}"
    existing = await _find_existing_research_ticket(linear_project_id=linear_project_id, title=resolved_title)
    if existing is not None:
        query_update = await service.get_query(name="update_issue")
        result_update = await service.graphql_request(
            query=query_update,
            variables={"id": existing["ticket_id"], "input": {"description": report}},
        )
        if result_update.get("errors"):
            raise LinearError(f"Failed to update research ticket description: {result_update['errors']}")
        data_update = (result_update or {}).get("data") or {}
        issue_update = data_update.get("issueUpdate") or {}
        if not issue_update.get("success"):
            raise LinearError("Failed to update research ticket description")
        updated_issue = issue_update.get("issue")
        if updated_issue:
            return {
                "ticket_id": updated_issue["id"],
                "identifier": updated_issue["identifier"],
                "title": updated_issue["title"],
            }
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
        raise LinearError(f"Failed to create research Linear ticket{detail}")

    issue = issue_create.get("issue")
    if not issue:
        raise LinearError("Linear API returned success but no issue data")

    return {
        "ticket_id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
    }
