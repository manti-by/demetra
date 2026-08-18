from typing import Any

from sqlalchemy import select

from demetra.library.exceptions import LinearError
from demetra.library.models import Context, LinearTask
from demetra.library.tables import projects
from demetra.services.linear.graphql import get_query, graphql_request
from demetra.services.persistence.database import get_connection, get_user_environments_decrypted
from demetra.services.runtime.tui import print_message
from demetra.settings import LINEAR


async def get_linear_config_value(name: str, *, user_id: str | None = None) -> str | None:
    """Resolve a Linear config value from the user-shared env or the settings.

    State names resolve to the matching ``LINEAR_STATE_<NAME>_ID`` key in the
    user's shared environment, ``"default_state"`` to ``LINEAR_DEFAULT_STATE_ID``
    and any other name to ``LINEAR_<NAME>``. The settings default is used when
    the user has no override for the key.

    Args:
        name: The config name, e.g. ``"team_id"``, ``"default_state"`` or a
            state name like ``"todo"``.
        user_id: Optional user id whose shared environment is consulted.

    Returns:
        str | None: The resolved value, or None when no layer provides it.
    """
    if name in LINEAR["states"]:
        env_key = f"LINEAR_STATE_{name.upper()}_ID"
    elif name == "default_state":
        env_key = "LINEAR_DEFAULT_STATE_ID"
    else:
        env_key = f"LINEAR_{name.upper()}"

    if user_id:
        user_environment = await get_user_environments_decrypted(user_id=user_id)
        if env_key in user_environment:
            return user_environment[env_key]

    states = {key: value for key, value in dict(LINEAR["states"]).items() if isinstance(value, str)}
    if name in states:
        return states[name]
    value = dict(LINEAR).get(name)
    return value if isinstance(value, str) else None


def extract_comments(issue: dict) -> list[str]:
    """Extract non-resolved comment bodies and their replies from an issue.

    Args:
        issue: The Linear issue GraphQL payload.

    Returns:
        list[str]: The comment bodies, including nested reply bodies.
    """
    result = []
    comments = issue.get("comments", {}).get("nodes", [])
    for comment in comments:
        if comment.get("resolvedAt"):
            continue
        result.append(comment.get("body", ""))
        for answer in comment.get("children", {}).get("edges", []):
            if answer_body := answer.get("node", {}).get("body", ""):
                result.append(answer_body)
    return result


def extract_labels(issue: dict) -> list[str]:
    """Extract the label names attached to a Linear issue.

    Args:
        issue: The Linear issue GraphQL payload.

    Returns:
        list[str]: The non-empty label names.
    """
    labels = issue.get("labels", {}).get("nodes", [])
    return [label["name"] for label in labels if label.get("name")]


async def get_linked_projects() -> dict[str, tuple[str, str]]:
    """Build a lookup of Linear project names and ids to Demetra projects.

    Returns:
        dict[str, tuple[str, str]]: Maps a lowercased Linear project id or
            name to a tuple of ``(project_id, user_id)``.
    """
    async with get_connection() as connection:
        result = await connection.execute(
            select(projects.c.id, projects.c.user_id, projects.c.linear_project_id, projects.c.name)
        )
        rows = result.fetchall()

    mapping: dict[str, tuple[str, str]] = {}
    for row in rows:
        if row.linear_project_id:
            mapping[row.linear_project_id.lower()] = (row.id, row.user_id)
        if row.name:
            mapping[row.name.lower()] = (row.id, row.user_id)
    return mapping


async def get_todo_issues(project_name: str | None = None, *, user_id: str | None = None) -> list[LinearTask]:
    """Fetch TODO issues from Linear, filtered by project and labels.

    Only issues belonging to a project are considered; an optional project
    name narrows the results, and configured filter labels are applied.

    Args:
        project_name: Optional Linear project name to filter on.
        user_id: Optional user id whose shared env overrides the TODO state.

    Returns:
        list[LinearTask]: The matching TODO issues as tasks.
    """
    state_id = await get_linear_config_value(name="todo", user_id=user_id)
    query = await get_query(name="get_all_issues")
    result = await graphql_request(query=query, variables={"state_id": state_id})
    issues = result.get("data", {}).get("issues", {}).get("nodes", [])

    linked_projects = await get_linked_projects()
    filter_labels = {label.lower() for label in LINEAR.get("filter_labels", [])}

    tasks = []
    for issue in issues:
        if not (project := issue.get("project", {})):
            print_message(f"There is no project associated with issue #{issue['identifier']}", style="info")
            continue

        linear_project_id = project.get("id", "").lower()
        issue_project_name = project.get("name", "").lower()

        if project_name is not None and project_name.lower() != issue_project_name:
            continue

        issue_labels = {name.lower() for name in extract_labels(issue)}
        if filter_labels and not any(label in issue_labels for label in filter_labels):
            continue

        resolved = linked_projects.get(linear_project_id) or linked_projects.get(issue_project_name)
        if resolved:
            project_id, user_id = resolved
        else:
            project_id, user_id = None, None

        tasks.append(
            LinearTask(
                id=issue["id"],
                identifier=issue["identifier"],
                title=issue["title"],
                description=issue.get("description", ""),
                priority=issue["priority"],
                created_at=issue["createdAt"],
                state="Todo",
                project_name=issue_project_name,
                project_id=project_id,
                user_id=user_id,
                comments=extract_comments(issue),
                labels=extract_labels(issue),
                url=issue.get("url"),
            )
        )
    return tasks


async def get_linear_task_by_id(task_id: str) -> LinearTask | None:
    """Fetch a single Linear task by its id.

    Args:
        task_id: The Linear issue id.

    Returns:
        LinearTask | None: The task, or None when the issue does not exist.
    """
    query = await get_query(name="get_issue_by_id")
    result = await graphql_request(query, {"issueId": task_id})
    issue = result.get("data", {}).get("issue", {})
    if not issue:
        return None

    linear_project_id = issue.get("project", {}).get("id", "").lower()
    project_name = issue.get("project", {}).get("name", "").lower()

    linked = await get_linked_projects()
    resolved = linked.get(linear_project_id) or linked.get(project_name)
    project_id, user_id = resolved if resolved else (None, None)

    return LinearTask(
        id=issue["id"],
        identifier=issue["identifier"],
        title=issue["title"],
        description=issue.get("description", ""),
        priority=issue["priority"],
        created_at=issue["createdAt"],
        project_name=project_name,
        project_id=project_id,
        user_id=user_id,
        comments=extract_comments(issue),
        labels=extract_labels(issue),
        url=issue.get("url"),
    )


async def get_linear_task(project_name: str, *, user_id: str | None = None) -> LinearTask | None:
    """Return the highest-priority TODO task for a project, if any.

    Tasks are sorted by priority and creation date before picking the first.

    Args:
        project_name: The Linear project name to filter on.
        user_id: Optional user id whose shared env overrides the TODO state.

    Returns:
        LinearTask | None: The selected task, or None when there are none.
    """
    issues = await get_todo_issues(project_name=project_name, user_id=user_id)
    issues = sorted(issues, key=lambda x: (-(x.priority or 0), x.created_at or ""), reverse=True)
    if issues:
        return issues[0]
    return None


async def update_ticket_status(task_id: str, state_id: str) -> bool:
    """Move a Linear issue to a given state.

    Args:
        task_id: The Linear issue id.
        state_id: The target Linear state id.

    Returns:
        bool: True when the update succeeded.
    """
    query = await get_query(name="update_issue_status")
    result = await graphql_request(query=query, variables={"issueId": task_id, "stateId": state_id})
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
    query = await get_query(name="create_issue_comment")
    result = await graphql_request(query=query, variables={"issueId": task_id, "body": body})
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
        print_message("Workflow complete", style="heading")
        state_id = await get_linear_config_value(name="in_review", user_id=context.project.user_id)
        if state_id is None:
            raise LinearError("Linear state 'in_review' is not configured")
        await update_ticket_status(task_id=context.linear_task.id, state_id=state_id)
        return

    print_message("Moving back a ticket in TODO column", style="heading")
    state_id = await get_linear_config_value(name="todo", user_id=context.project.user_id)
    if state_id is None:
        raise LinearError("Linear state 'todo' is not configured")
    await update_ticket_status(task_id=context.linear_task.id, state_id=state_id)


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

    query = await get_query(name="create_issue")
    variables = {
        "input": {
            "title": title,
            "description": full_description,
            "teamId": team_id or await get_linear_config_value(name="team_id", user_id=user_id),
            "stateId": state_id or await get_linear_config_value(name="default_state", user_id=user_id),
            "projectId": project_id,
            "labelIds": [LINEAR["feature_label_id"]],
            "createAsUser": "Demetra",
            "priority": 3,
        }
    }
    result = await graphql_request(query=query, variables=variables)

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
