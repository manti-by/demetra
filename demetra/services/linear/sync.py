"""Backfill of the local Linear mirror.

The backfill pulls every issue of the Linear projects linked to Demetra
projects, together with their comments, and stores them as generic tasks and
messages. Every write is idempotent, so the sync can be re-run at any time.
"""

from dataclasses import dataclass, field

from demetra.library.exceptions import LinearError
from demetra.services.linear.mirror import (
    fetch_issue_comments,
    fetch_project_issues,
    store_linear_issue,
)
from demetra.services.linear.tasks import get_linked_projects
from demetra.services.persistence.database import list_linked_linear_projects
from demetra.services.runtime.tui import print_message


@dataclass
class SyncReport:
    """Counters collected while mirroring the Linear projects.

    Attributes:
        projects: The number of Linear projects that were walked.
        issues: The number of issues that were mirrored.
        comments: The number of comments that were mirrored.
    """

    projects: int = 0
    issues: int = 0
    comments: int = 0
    failures: list[str] = field(default_factory=list)


async def sync_linear_mirror(*, dry_run: bool = False) -> SyncReport:
    """Mirror every issue of the linked Linear projects into the local store.

    A project or an issue that cannot be read is recorded as a failure and the
    backfill continues, so a partial run keeps the results it already
    mirrored.

    Args:
        dry_run: When True, the issues are counted but nothing is written.

    Returns:
        SyncReport: The counters of the run.
    """
    report = SyncReport()
    linked = await get_linked_projects()
    for linear_project_id in await list_linked_linear_projects():
        resolved = linked.get(linear_project_id.lower())
        project_id, user_id = resolved if resolved else (None, None)
        report.projects += 1
        print_message(f"Syncing Linear project {linear_project_id}", style="info")
        try:
            issues = await fetch_project_issues(linear_project_id)
        except (RuntimeError, LinearError) as error:
            report.failures.append(f"{linear_project_id}: {error}")
            continue
        for issue in issues:
            issue_id = issue.get("id")
            if not issue_id:
                continue
            try:
                comments = await fetch_issue_comments(issue_id)
            except (RuntimeError, LinearError) as error:
                report.failures.append(f"{issue_id}: {error}")
                continue
            report.issues += 1
            report.comments += len(comments)
            if dry_run:
                continue
            payload = {**issue, "comments": {"nodes": comments}}
            await store_linear_issue(issue=payload, project_id=project_id, user_id=user_id)
    return report


async def sync_cli(dry_run: bool) -> int:
    """Run the Linear mirror backfill.

    Args:
        dry_run: When True, the issues are counted but nothing is written.

    Returns:
        int: The process exit code.
    """
    try:
        report = await sync_linear_mirror(dry_run=dry_run)
    except LinearError as error:
        print_message(f"Linear sync failed: {error}", style="error")
        return 1
    prefix = "(dry-run) " if dry_run else ""
    print_message(
        f"{prefix}synced {report.issues} issues and {report.comments} comments from {report.projects} Linear projects",
        style="result",
    )
    for failure in report.failures:
        print_message(f"Failed: {failure}", style="error")
    return 1 if report.failures else 0
