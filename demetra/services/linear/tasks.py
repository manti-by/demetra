import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

import demetra.services.linear as service
from demetra.library.models import LinearTask, Message, SessionEnvironment
from demetra.library.tables import projects
from demetra.services.linear.mirror import store_linear_issue


logger = logging.getLogger(__name__)


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


def _resolve_ownership(issue: dict, linked_projects: dict[str, tuple[str, str]]) -> tuple[str | None, str | None]:
    """Resolve the Demetra project and user a Linear issue maps to.

    Args:
        issue: The Linear issue GraphQL payload.
        linked_projects: The linked project lookup.

    Returns:
        tuple[str | None, str | None]: The project id and user id, or
            ``(None, None)`` when the issue maps to no known project.
    """
    linear_project_id = (issue.get("project") or {}).get("id", "").lower()
    project_name = (issue.get("project") or {}).get("name", "").lower()
    resolved = linked_projects.get(linear_project_id) or linked_projects.get(project_name)
    return resolved if resolved else (None, None)


def build_context_messages(issue: dict) -> list[Message]:
    """Build the context messages of a Linear issue.

    Only non-resolved comments and their replies feed the agent context, the
    same way chat turns do for a chat-mode task.

    Args:
        issue: The Linear issue GraphQL payload.

    Returns:
        list[Message]: The context messages, in recording order.
    """
    bodies = extract_comments(issue)
    return [
        Message(
            id=f"linear-context-{index}",
            task_id=issue["id"],
            body=body,
            created_at=issue.get("createdAt") or "",
            source="linear",
            kind="comment",
        )
        for index, body in enumerate(bodies)
    ]


def _build_linear_task(issue: dict, *, project_id: str | None, user_id: str | None) -> LinearTask:
    """Build a Linear task record from a Linear issue payload.

    Args:
        issue: The Linear issue GraphQL payload.
        project_id: The Demetra project the issue maps to.
        user_id: The Demetra user the issue maps to.

    Returns:
        LinearTask: The task record.
    """
    state = issue.get("state") or {}
    linear_project = issue.get("project") or {}
    return LinearTask(
        id=issue["id"],
        identifier=issue["identifier"],
        title=issue["title"],
        description=issue.get("description", ""),
        priority=issue.get("priority") or 0,
        created_at=issue.get("createdAt"),
        state=state.get("name"),
        project_name=linear_project.get("name"),
        project_id=project_id,
        linear_project_id=(linear_project.get("id") or "").lower() or None,
        user_id=user_id,
        tags=extract_labels(issue),
        url=issue.get("url"),
        messages=build_context_messages(issue),
        linear_issue_id=issue["id"],
        linear_identifier=issue["identifier"],
        linear_state_id=state.get("id"),
        linear_state_name=state.get("name"),
        branch_name=issue.get("branchName"),
    )


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
    user_environment = await service.get_user_environments_decrypted(user_id=user_id) if user_id else {}
    environment = SessionEnvironment(project_environment={}, user_environment=user_environment)
    state_id = environment.linear_state("todo")
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

        tasks.append(_build_linear_task(issue, project_id=project_id, user_id=user_id))
    return tasks


async def get_linear_task_by_id(task_id: str) -> LinearTask | None:
    """Fetch a single Linear task by its id.

    The issue is fetched live from Linear and mirrored into the local task
    store, so the conversation history of a worked-on ticket is kept locally.

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

    linked = await service.get_linked_projects()
    project_id, user_id = _resolve_ownership(issue, linked)

    task = _build_linear_task(issue, project_id=project_id, user_id=user_id)
    try:
        await store_linear_issue(issue=issue, project_id=project_id, user_id=user_id)
    except SQLAlchemyError:
        logger.warning("Failed to mirror Linear issue %s into the local task store", task_id, exc_info=True)
    return task


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
