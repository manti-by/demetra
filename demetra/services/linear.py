from demetra.models import Context, LinearIssue
from demetra.services.graphql import get_query, graphql_request
from demetra.services.tui import print_message
from demetra.settings import LINEAR_STATE_IN_REVIEW_ID, LINEAR_STATE_TODO_ID, LINEAR_TEAM_ID


async def get_todo_issues(project_name: str) -> list[LinearIssue]:
    query = await get_query(name="get_todo_issues")
    result = await graphql_request(query, {"teamId": LINEAR_TEAM_ID})
    states = result.get("data", {}).get("team", {}).get("states", {}).get("nodes", [])

    issues = []
    for state in states:
        if state["name"].lower() == "todo":
            for issue in state["issues"]["nodes"]:
                if issue.get("project", {}).get("name", "").lower() == project_name.lower():
                    issues.append(
                        LinearIssue(
                            id=issue["id"],
                            identifier=issue["identifier"],
                            title=issue["title"],
                            description=issue.get("description", ""),
                            priority=issue["priority"],
                            created_at=issue["createdAt"],
                            branch_name=issue["branchName"],
                        )
                    )
    return issues


async def get_linear_task(project_name: str) -> LinearIssue | None:
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
