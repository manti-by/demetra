from datetime import UTC, datetime
from typing import Any

import demetra.services.clickup as service
from demetra.library.exceptions import ClickUpConfigError, EnvironmentConfigError
from demetra.library.models import LinearTask, SessionEnvironment


TASKS_PAGE_LIMIT = 20


def extract_labels(task: dict) -> list[str]:
    """Extract the tag names attached to a ClickUp task.

    Args:
        task: The ClickUp task payload.

    Returns:
        list[str]: The non-empty tag names.
    """
    return [tag["name"] for tag in task.get("tags") or [] if tag.get("name")]


def extract_comments(comments: list[dict], replies: dict[str, list[dict]] | None = None) -> list[str]:
    """Extract non-resolved comment bodies and their threaded replies.

    The ClickUp comments endpoint returns newest first; the result is
    reordered oldest first so the task text reads chronologically, matching
    the Linear renderer.

    Args:
        comments: The top-level comment payloads for a task.
        replies: Optional mapping of comment id to its threaded reply payloads.

    Returns:
        list[str]: The comment bodies, including nested reply bodies.
    """
    replies = replies or {}
    result: list[str] = []
    for comment in reversed(comments):
        if comment.get("resolved"):
            continue
        result.append(comment.get("comment_text", ""))
        for reply in reversed(replies.get(str(comment.get("id")), [])):
            if reply_body := reply.get("comment_text", ""):
                result.append(reply_body)
    return result


def parse_priority(task: dict) -> int:
    """Return the task priority as an int, ``0`` when unset.

    ClickUp priorities share Linear's scale (1 urgent, 2 high, 3 normal,
    4 low) but arrive as a nested object with a string ``id``.

    Args:
        task: The ClickUp task payload.

    Returns:
        int: The numeric priority, or 0 when the task has none.
    """
    priority = task.get("priority")
    if not isinstance(priority, dict):
        return 0
    try:
        return int(priority.get("id") or 0)
    except (TypeError, ValueError):
        return 0


def parse_created_at(task: dict) -> str:
    """Convert the millisecond epoch ``date_created`` into an ISO timestamp.

    Args:
        task: The ClickUp task payload.

    Returns:
        str: The ISO 8601 creation timestamp, or ``""`` when missing.
    """
    raw = task.get("date_created")
    if not raw:
        return ""
    try:
        return datetime.fromtimestamp(int(raw) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return ""


async def fetch_task_comments(task_id: str) -> list[str]:
    """Fetch the comment bodies of a task, including threaded replies.

    Args:
        task_id: The ClickUp task id.

    Returns:
        list[str]: The unresolved comment bodies, oldest first.
    """
    payload = await service.clickup_request(method="GET", path=f"/task/{task_id}/comment")
    comments = payload.get("comments") or []
    replies: dict[str, list[dict]] = {}
    for comment in comments:
        try:
            reply_count = int(comment.get("reply_count") or 0)
        except (TypeError, ValueError):
            reply_count = 0
        if reply_count > 0 and comment.get("id"):
            thread = await service.clickup_request(method="GET", path=f"/comment/{comment['id']}/reply")
            replies[str(comment["id"])] = thread.get("comments") or []
    return extract_comments(comments=comments, replies=replies)


def build_task(task: dict, linked_projects: dict[str, tuple[str, str]], comments: list[str]) -> LinearTask:
    """Build a :class:`LinearTask` from a ClickUp task payload.

    The ClickUp list plays the role of the Linear project: its id is stored
    in ``linear_project_id`` and matched against ``projects.linear_project_id``
    (or the project name) to resolve the Demetra project and owner.

    Args:
        task: The ClickUp task payload.
        linked_projects: Lookup of lowercased list id or name to
            ``(project_id, user_id)``.
        comments: The already-fetched comment bodies.

    Returns:
        LinearTask: The tracker-neutral task.
    """
    task_list = task.get("list") or {}
    list_id = str(task_list.get("id") or "").lower()
    list_name = str(task_list.get("name") or "").lower()
    resolved = linked_projects.get(list_id) or linked_projects.get(list_name)
    project_id, user_id = resolved if resolved else (None, None)

    status = task.get("status") or {}
    return LinearTask(
        id=task["id"],
        identifier=task.get("custom_id") or task["id"],
        title=task.get("name", ""),
        description=task.get("markdown_description") or task.get("description") or "",
        priority=parse_priority(task),
        created_at=parse_created_at(task),
        state=status.get("status") if isinstance(status, dict) else None,
        project_name=list_name or None,
        project_id=project_id,
        linear_project_id=list_id or None,
        user_id=user_id,
        comments=comments,
        labels=extract_labels(task),
        url=task.get("url"),
    )


async def _resolve_environment(user_id: str | None, environment: SessionEnvironment | None) -> SessionEnvironment:
    """Return the environment to resolve ClickUp config through.

    Args:
        user_id: Optional user id whose shared env is loaded when no
            environment is given.
        environment: An already-resolved environment, if any.

    Returns:
        SessionEnvironment: The resolver to use.
    """
    if environment is not None:
        return environment
    user_environment = await service.get_user_environments_decrypted(user_id=user_id) if user_id else {}
    return SessionEnvironment(project_environment={}, user_environment=user_environment)


async def list_team_tasks(team_id: str, params: list[tuple[str, Any]]) -> list[dict]:
    """Page through the filtered team tasks endpoint.

    Args:
        team_id: The ClickUp workspace (team) id.
        params: The filter query parameters, excluding ``page``.

    Returns:
        list[dict]: Every task payload across all pages.
    """
    tasks: list[dict] = []
    for page in range(TASKS_PAGE_LIMIT):
        payload = await service.clickup_request(
            method="GET", path=f"/team/{team_id}/task", params=[*params, ("page", page)]
        )
        page_tasks = payload.get("tasks") or []
        tasks.extend(page_tasks)
        if payload.get("last_page", True) or not page_tasks:
            break
    return tasks


async def get_todo_issues(
    project_name: str | None = None,
    *,
    user_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> list[LinearTask]:
    """Fetch TODO tasks from ClickUp, filtered by list and tags.

    Queries the workspace-wide filtered tasks endpoint for the configured
    ``todo`` status; an optional project (list) name narrows the results and
    configured filter labels are applied against task tags.

    Args:
        project_name: Optional ClickUp list name to filter on.
        user_id: Optional user id whose shared env overrides the config.
        environment: Optional resolved environment; built from the user env
            when omitted.

    Returns:
        list[LinearTask]: The matching TODO tasks.

    Raises:
        ClickUpConfigError: When the workspace id is not configured.
    """
    environment = await _resolve_environment(user_id=user_id, environment=environment)
    try:
        team_id = environment.clickup_value("team_id")
    except EnvironmentConfigError as e:
        raise ClickUpConfigError("CLICKUP_TEAM_ID is not configured") from e
    todo_state = environment.clickup_state("todo")

    params: list[tuple[str, Any]] = [
        ("statuses[]", todo_state),
        ("include_closed", "false"),
        ("subtasks", "true"),
        ("order_by", "created"),
    ]
    raw_tasks = await list_team_tasks(team_id=team_id, params=params)

    linked_projects = await service.get_linked_projects()
    filter_labels = {label.lower() for label in service.CLICKUP.get("filter_labels", [])}

    tasks: list[LinearTask] = []
    for raw in raw_tasks:
        task_list = raw.get("list") or {}
        if not task_list.get("id"):
            service.print_message(f"There is no list associated with task #{raw.get('id')}", style="info")
            continue

        list_name = str(task_list.get("name") or "").lower()
        if project_name is not None and project_name.lower() != list_name:
            continue

        task_labels = {name.lower() for name in extract_labels(raw)}
        if filter_labels and not any(label in task_labels for label in filter_labels):
            continue

        comments = await fetch_task_comments(task_id=raw["id"])
        tasks.append(build_task(task=raw, linked_projects=linked_projects, comments=comments))
    return tasks


async def get_clickup_task_by_id(task_id: str) -> LinearTask | None:
    """Fetch a single ClickUp task by its id.

    Args:
        task_id: The ClickUp task id.

    Returns:
        LinearTask | None: The task, or None when it does not exist.
    """
    payload = await service.clickup_request(
        method="GET", path=f"/task/{task_id}", params={"include_markdown_description": "true"}
    )
    if not payload.get("id"):
        return None

    linked_projects = await service.get_linked_projects()
    comments = await fetch_task_comments(task_id=payload["id"])
    return build_task(task=payload, linked_projects=linked_projects, comments=comments)


async def get_clickup_task(
    project_name: str,
    *,
    user_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> LinearTask | None:
    """Return the highest-priority TODO task for a list, if any.

    Args:
        project_name: The ClickUp list name to filter on.
        user_id: Optional user id whose shared env overrides the config.
        environment: Optional resolved environment.

    Returns:
        LinearTask | None: The selected task, or None when there are none.
    """
    issues = await get_todo_issues(project_name=project_name, user_id=user_id, environment=environment)
    issues = sorted(issues, key=lambda x: (-(x.priority or 0), x.created_at or ""), reverse=True)
    if issues:
        return issues[0]
    return None
