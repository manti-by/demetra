from typing import Any

from sqlalchemy import select

from demetra.library.exceptions import LinearError
from demetra.library.models import Context, LinearTask
from demetra.library.tables import projects
from demetra.services.database import get_connection
from demetra.services.graphql import get_query, graphql_request
from demetra.services.tui import print_message
from demetra.settings import LINEAR


def extract_comments(issue: dict) -> list[str]:
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
    labels = issue.get("labels", {}).get("nodes", [])
    return [label["name"] for label in labels if label.get("name")]


async def get_linked_projects() -> dict[str, tuple[str, str]]:
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


async def get_todo_issues(project_name: str | None = None) -> list[LinearTask]:
    query = await get_query(name="get_all_issues")
    result = await graphql_request(query=query, variables={"state_id": LINEAR["states"]["todo"]})
    issues = result.get("data", {}).get("issues", {}).get("nodes", [])

    linked = await get_linked_projects()
    tasks = []
    for issue in issues:
        if not (project := issue.get("project", {})):
            print_message(f"There is no project associated with issue #{issue['identifier']}", style="info")
            continue

        linear_project_id = project.get("id", "").lower()
        issue_project_name = project.get("name", "").lower()

        if project_name is not None and project_name.lower() != issue_project_name:
            continue

        resolved = linked.get(linear_project_id) or linked.get(issue_project_name)
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
            )
        )
    return tasks


async def get_linear_task_by_id(task_id: str) -> LinearTask | None:
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
    )


async def get_linear_task(project_name: str) -> LinearTask | None:
    issues = await get_todo_issues(project_name=project_name)
    issues = sorted(issues, key=lambda x: (-(x.priority or 0), x.created_at or ""), reverse=True)
    if issues:
        return issues[0]
    return None


async def update_ticket_status(task_id: str, state_id: str) -> bool:
    query = await get_query(name="update_issue_status")
    result = await graphql_request(query=query, variables={"issueId": task_id, "stateId": state_id})
    return result.get("data", {}).get("issueUpdate", {}).get("success", False)


async def post_comment(task_id: str, body: str) -> bool:
    query = await get_query(name="create_issue_comment")
    result = await graphql_request(query=query, variables={"issueId": task_id, "body": body})
    return result.get("data", {}).get("commentCreate", {}).get("success", False)


async def linear_cleanup(context: Context, is_success: bool):
    if is_success:
        print_message("Workflow complete", style="heading")
        await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["in_review"])
        return

    print_message("Moving back a ticket in TODO column", style="heading")
    await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["todo"])


async def create_linear_ticket(
    title: str,
    description: str,
    technical_requirements: str,
    acceptance_criteria: str,
    team_id: str | None = None,
    state_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
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
            "teamId": team_id or LINEAR["team_id"],
            "stateId": state_id or LINEAR["default_state"],
            "projectId": project_id or LINEAR["default_project"],
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
