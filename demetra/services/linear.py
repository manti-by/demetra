from demetra.models import Context, LinearTask
from demetra.services.graphql import get_query, graphql_request
from demetra.services.tui import print_message
from demetra.settings import LINEAR_STATE_IN_REVIEW_ID, LINEAR_STATE_TODO_ID, LINEAR_TEAM_ID


async def get_todo_issues(project_name: str | None = None) -> list[LinearTask]:
    query = await get_query(name="get_todo_issues")
    result = await graphql_request(query, {"teamId": LINEAR_TEAM_ID})
    states = result.get("data", {}).get("team", {}).get("states", {}).get("nodes", [])

    issues = []
    for state in states:
        if state["name"].lower() == "todo":
            for issue in state["issues"]["nodes"]:
                issue_project_name = None
                if project := issue.get("project", {}):
                    issue_project_name = project.get("name", "").lower()
                if project_name is None or project_name.lower() == issue_project_name:
                    issues.append(
                        LinearTask(
                            id=issue["id"],
                            identifier=issue["identifier"],
                            title=issue["title"],
                            description=issue.get("description", ""),
                            priority=issue["priority"],
                            created_at=issue["createdAt"],
                            branch_name=issue["branchName"],
                            project_name=issue_project_name,
                        )
                    )
    return issues


async def get_linear_task_by_id(task_id: str) -> LinearTask | None:
    query = await get_query(name="get_issue_by_id")
    result = await graphql_request(query, {"issueId": task_id})
    issue = result.get("data", {}).get("issue", {})
    if not issue:
        return None
    project_name = None
    if project := issue.get("project", {}):
        project_name = project.get("name", "").lower()
    return LinearTask(
        id=issue["id"],
        identifier=issue["identifier"],
        title=issue["title"],
        description=issue.get("description", ""),
        priority=issue["priority"],
        created_at=issue["createdAt"],
        branch_name=issue["branchName"],
        project_name=project_name,
    )


async def get_linear_task(project_name: str) -> LinearTask | None:
    issues = await get_todo_issues(project_name=project_name)
    issues = sorted(issues, key=lambda x: (-(x.priority or 0), x.created_at or ""), reverse=True)
    if issues:
        return issues[0]
    return None


async def update_ticket_status(task_id: str, state_id: str) -> bool:
    query = await get_query(name="update_issue_status")
    result = await graphql_request(query, {"issueId": task_id, "stateId": state_id})
    return result.get("data", {}).get("issueUpdate", {}).get("success", False)


async def post_comment(task_id: str, body: str) -> bool:
    query = await get_query(name="create_issue_comment")
    result = await graphql_request(query, {"issueId": task_id, "body": body})
    return result.get("data", {}).get("commentCreate", {}).get("success", False)


async def linear_cleanup(context: Context, is_success: bool):
    if is_success:
        print_message("Workflow complete", style="heading")
        await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR_STATE_IN_REVIEW_ID)
        return

    print_message("Moving back a ticket in TODO column", style="heading")
    await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR_STATE_TODO_ID)
