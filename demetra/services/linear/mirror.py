"""Local mirror of Linear issues and their comments.

The mirror stores Linear issues as generic tasks with a ``linear_tasks``
subtype row, and Linear comments as ``messages`` rows keyed by their Linear
comment id. Writes are idempotent so the mirror can be refreshed at any time.
"""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError

from demetra.library.models import ChatMessageKind, LinearTask, Message
from demetra.services.linear.graphql import get_query, graphql_request
from demetra.services.persistence.database import (
    post_message,
    upsert_message,
    upsert_task_with_linear,
)


logger = logging.getLogger(__name__)


ISSUE_PAGE_SIZE = 50
COMMENT_PAGE_SIZE = 50
COMMENT_STORE_ATTEMPTS = 3
COMMENT_STORE_BACKOFF_SECONDS = 0.2


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse a Linear ISO timestamp.

    Args:
        value: The timestamp string, e.g. ``"2026-11-10T21:14:24.895Z"``.

    Returns:
        datetime | None: The parsed timestamp, or None when the value is
            missing or malformed.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def extract_comment_threads(issue: dict) -> list[dict]:
    """Extract every comment of an issue, including its threaded replies.

    Args:
        issue: The Linear issue GraphQL payload.

    Returns:
        list[dict]: One entry per comment with its ``id``, ``body``,
            ``created_at``, ``author_name`` and ``parent_id``.
    """
    comments: list[dict] = []
    for node in issue.get("comments", {}).get("nodes", []):
        comments.append(_comment_row(node, parent_id=None))
        for edge in node.get("children", {}).get("edges", []):
            child = edge.get("node") or {}
            if child.get("body"):
                comments.append(_comment_row(child, parent_id=node.get("id")))
    return comments


def _comment_row(node: dict, parent_id: str | None) -> dict:
    """Convert a Linear comment node into a mirror row.

    Args:
        node: The Linear comment node.
        parent_id: The id of the parent comment, or None for a top-level one.

    Returns:
        dict: The comment row.
    """
    return {
        "id": node.get("id"),
        "body": node.get("body") or "",
        "created_at": node.get("createdAt"),
        "author_name": (node.get("user") or {}).get("name"),
        "parent_id": parent_id,
    }


async def record_linear_comment(
    *,
    task_id: str,
    body: str,
    kind: ChatMessageKind = "comment",
    external_id: str | None = None,
) -> Message | None:
    """Store a comment Demetra posted to Linear in the local message history.

    The local copy is a mirror of a comment Linear already accepted, so a
    storage failure is logged and swallowed: it must not stop the caller from
    applying the state change the comment announced. The write is retried
    because it is keyed by the Linear comment id and therefore idempotent, so
    a retry restores the copy under the same external id instead of creating
    a second message.

    Args:
        task_id: The task the comment belongs to.
        body: The comment body.
        kind: The message kind.
        external_id: The Linear comment id, when the API returned one.

    Returns:
        Message | None: The stored message record, or None when it could not
            be stored.
    """
    for attempt in range(COMMENT_STORE_ATTEMPTS):
        try:
            if isinstance(external_id, str) and external_id:
                return await upsert_message(
                    task_id=task_id,
                    body=body,
                    external_id=external_id,
                    kind=kind,
                    source="linear",
                )
            return await post_message(task_id=task_id, body=body, kind=kind, source="linear", is_system=True)
        except (SQLAlchemyError, OSError):
            logger.warning("Failed to store the Linear comment of task %s locally", task_id, exc_info=True)
            if attempt < COMMENT_STORE_ATTEMPTS - 1:
                await asyncio.sleep(COMMENT_STORE_BACKOFF_SECONDS * (attempt + 1))
    return None


async def store_linear_issue(
    *,
    issue: dict,
    project_id: str | None = None,
    user_id: str | None = None,
) -> LinearTask:
    """Mirror a Linear issue and its comments into the local task store.

    Args:
        issue: The Linear issue GraphQL payload.
        project_id: Optional Demetra project the issue maps to.
        user_id: Optional Demetra user the issue maps to.

    Returns:
        LinearTask: The mirrored task record.
    """
    issue_id = issue["id"]
    state = issue.get("state") or {}
    linear_project = issue.get("project") or {}
    linear_project_id = (linear_project.get("id") or "").lower() or None
    labels = [label["name"] for label in (issue.get("labels") or {}).get("nodes", []) if label.get("name")]

    values = {
        "id": issue_id,
        "kind": "linear",
        "identifier": issue.get("identifier") or issue_id,
        "title": issue.get("title") or "",
        "description": issue.get("description") or "",
        "priority": issue.get("priority") or 0,
        "state": state.get("name"),
        "url": issue.get("url"),
        "tags": labels,
    }
    if project_id is not None:
        values["project_id"] = project_id
    if user_id is not None:
        values["user_id"] = user_id

    task = await upsert_task_with_linear(
        values,
        {
            "task_id": issue_id,
            "linear_issue_id": issue_id,
            "linear_identifier": issue.get("identifier"),
            "linear_state_id": state.get("id"),
            "linear_state_name": state.get("name"),
            "linear_project_id": linear_project_id,
            "branch_name": issue.get("branchName"),
        },
    )
    await store_linear_comments(task_id=issue_id, issue=issue)
    return LinearTask(
        id=task.id,
        identifier=task.identifier,
        title=task.title,
        description=task.description,
        priority=task.priority,
        state=task.state,
        url=task.url,
        tags=task.tags,
        project_id=task.project_id,
        project_name=task.project_name,
        user_id=task.user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
        linear_issue_id=issue_id,
        linear_identifier=issue.get("identifier"),
        linear_state_id=state.get("id"),
        linear_state_name=state.get("name"),
        linear_project_id=linear_project_id,
        branch_name=issue.get("branchName"),
    )


async def store_linear_comments(*, task_id: str, issue: dict) -> int:
    """Mirror the comments of a Linear issue into the message store.

    Args:
        task_id: The task the comments belong to.
        issue: The Linear issue GraphQL payload.

    Returns:
        int: The number of comments stored.
    """
    stored = 0
    local_ids: dict[str, str] = {}
    for comment in extract_comment_threads(issue):
        if not comment["id"]:
            continue
        message = await upsert_message(
            task_id=task_id,
            body=comment["body"],
            external_id=comment["id"],
            kind="comment",
            source="linear",
            author_name=comment["author_name"],
            parent_id=local_ids.get(comment["parent_id"]) if comment["parent_id"] else None,
            created_at=parse_timestamp(comment["created_at"]),
        )
        local_ids[comment["id"]] = message.id
        stored += 1
    return stored


async def fetch_project_issues(linear_project_id: str) -> list[dict]:
    """Fetch every issue of a Linear project, following the cursor.

    Args:
        linear_project_id: The Linear project id.

    Returns:
        list[dict]: The issue payloads.
    """
    query = await get_query(name="get_project_issues")
    issues: list[dict] = []
    after: str | None = None
    while True:
        payload = await graphql_request(query, {"projectId": linear_project_id, "after": after})
        if payload.get("errors"):
            raise RuntimeError(f"Linear API error: {payload['errors']}")
        connection = (payload.get("data") or {}).get("issues") or {}
        issues.extend(connection.get("nodes") or [])
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break
    return issues


async def fetch_comment_replies(comment_id: str, after: str | None = None) -> list[dict]:
    """Fetch the replies of a comment that follow a cursor.

    The issue query already returns the first page of replies inline; this
    walks the remaining pages of a comment whose replies overflow one page.

    Args:
        comment_id: The Linear comment id.
        after: The cursor to resume from, or None to start at the beginning.

    Returns:
        list[dict]: The reply nodes.
    """
    query = await get_query(name="get_comment_replies")
    replies: list[dict] = []
    while True:
        payload = await graphql_request(query, {"commentId": comment_id, "after": after})
        if payload.get("errors"):
            raise RuntimeError(f"Linear API error: {payload['errors']}")
        connection = ((payload.get("data") or {}).get("comment") or {}).get("children") or {}
        replies.extend((edge.get("node") or {}) for edge in connection.get("edges") or [])
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break
    return replies


async def fetch_issue_comments(issue_id: str) -> list[dict]:
    """Fetch every comment of a Linear issue, following the cursor.

    The replies of a top-level comment are fetched with their own cursor, so a
    thread longer than one page is not truncated.

    Args:
        issue_id: The Linear issue id.

    Returns:
        list[dict]: The comment nodes, including threaded replies.
    """
    query = await get_query(name="get_issue_comments")
    comments: list[dict] = []
    after: str | None = None
    while True:
        payload = await graphql_request(query, {"issueId": issue_id, "after": after})
        if payload.get("errors"):
            raise RuntimeError(f"Linear API error: {payload['errors']}")
        connection = ((payload.get("data") or {}).get("issue") or {}).get("comments") or {}
        nodes = connection.get("nodes") or []
        for node in nodes:
            node["children"] = {"edges": await _fetch_comment_edges(node)}
        comments.extend(nodes)
        page_info = connection.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after = page_info.get("endCursor")
        if not after:
            break
    return comments


async def _fetch_comment_edges(comment: dict) -> list[dict]:
    """Return every reply of a comment, following the reply cursor.

    Args:
        comment: The Linear comment node.

    Returns:
        list[dict]: The reply edges.
    """
    children = comment.get("children") or {}
    edges = list(children.get("edges") or [])
    page_info = children.get("pageInfo") or {}
    if not page_info.get("hasNextPage"):
        return edges
    comment_id = comment.get("id")
    if not comment_id:
        return edges
    remaining = await fetch_comment_replies(comment_id=comment_id, after=page_info.get("endCursor"))
    edges.extend({"node": reply} for reply in remaining)
    return edges
