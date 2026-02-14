from demetra.models import LinearIssue
from demetra.services.graphql import get_todo_issues_query, graphql_request
from demetra.settings import LINEAR_TEAM_ID


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
