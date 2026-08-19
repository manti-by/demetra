from sqlalchemy import select

import demetra.services.linear as service
from demetra.library.models import LinearTask
from demetra.library.tables import projects


async def get_linked_projects() -> dict[str, tuple[str, str]]:
    """Build a lookup of Linear project names and ids to Demetra projects.

    Returns:
        dict[str, tuple[str, str]]: Maps a lowercased Linear project id or
            name to a tuple of ``(project_id, user_id)``.
    """
    async with service.get_connection() as connection:
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
    state_id = await service.get_linear_config_value(name="todo", user_id=user_id)
    query = await service.get_query(name="get_all_issues")
    result = await service.graphql_request(query=query, variables={"state_id": state_id})
    issues = result.get("data", {}).get("issues", {}).get("nodes", [])

    linked_projects = await service.get_linked_projects()
    filter_labels = {label.lower() for label in service.LINEAR.get("filter_labels", [])}

    tasks = []
    for issue in issues:
        if not (project := issue.get("project", {})):
            service.print_message(f"There is no project associated with issue #{issue['identifier']}", style="info")
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
    query = await service.get_query(name="get_issue_by_id")
    result = await service.graphql_request(query, {"issueId": task_id})
    issue = result.get("data", {}).get("issue", {})
    if not issue:
        return None

    linear_project_id = issue.get("project", {}).get("id", "").lower()
    project_name = issue.get("project", {}).get("name", "").lower()

    linked = await service.get_linked_projects()
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
