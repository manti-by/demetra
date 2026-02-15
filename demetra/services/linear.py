import aiofiles

from demetra.models import LinearIssue
from demetra.services.graphql import get_todo_issues_query, graphql_request
from demetra.settings import BASE_PATH, LINEAR_TEAM_ID


async def get_todo_issues(project_name: str) -> list[LinearIssue]:
    query = await get_todo_issues_query()
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
    issues = sorted(issues, key=lambda x: (x.priority or 10, x.created_at or ""))
    if issues:
        return issues[0]
    return None


async def get_update_issue_mutation() -> str:
    async with aiofiles.open(BASE_PATH / "demetra" / "services" / "queries" / "update_issue_status.gql") as file:
        content = await file.read()
    return content


async def update_ticket_status(issue_id: str, state_id: str) -> bool:
    try:
        query = await get_update_issue_mutation()
        result = await graphql_request(query, {"issueId": issue_id, "stateId": state_id})
        return result.get("data", {}).get("issueUpdate", {}).get("success", False)
    except BaseException:  # noqa: BLE001
        return False
