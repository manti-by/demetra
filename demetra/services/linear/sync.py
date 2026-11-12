"""Backfill of the local Linear mirror.

The backfill pulls every issue of the Linear projects linked to Demetra
projects, together with their comments, and stores them as generic tasks and
messages. Every write is idempotent, so the sync can be re-run at any time.
"""

from dataclasses import dataclass, field

from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import LinearError
from demetra.services.linear.mirror import (
    extract_comment_rows,
    fetch_issue_comments,
    fetch_linear_project_id,
    fetch_project_issues,
    store_linear_issue,
)
from demetra.services.persistence.database import (
    list_linked_linear_projects,
    list_name_only_linear_projects,
)
from demetra.services.runtime.tui import print_message


@dataclass
class SyncReport:
    """Counters collected while mirroring the Linear projects.

    Attributes:
        projects: The number of Linear projects that were walked.
        issues: The number of issues that were mirrored.
        comments: The number of comments that were mirrored.
        pending_issues: The number of issues a dry run would mirror.
        pending_comments: The number of comments a dry run would mirror.
    """

    projects: int = 0
    issues: int = 0
    comments: int = 0
    pending_issues: int = 0
    pending_comments: int = 0
    failures: list[str] = field(default_factory=list)


async def resolve_sync_targets(*, report: SyncReport) -> list[tuple[str, str, str]]:
    """Resolve the Linear projects the backfill has to walk.

    Every project linked by its Linear id is walked directly. A project linked
    by name only is resolved to its Linear id first, so its issues are mirrored
    as well. Every target carries the identity of the project that owns the
    link, so the issues are never stored under the owner of another project.

    Args:
        report: The report the failures are recorded in.

    Returns:
        list[tuple[str, str, str]]: The Linear project id and the Demetra
            project and user it belongs to.
    """
    targets: list[tuple[str, str, str]] = []
    walked: dict[str, str] = {}

    for project in await list_linked_linear_projects():
        linear_project_id = project["linear_project_id"]
        key = linear_project_id.lower()
        if key in walked:
            report.failures.append(f"{linear_project_id}: {walked[key]} and {project['id']} share this Linear project")
            continue
        walked[key] = project["id"]
        targets.append((linear_project_id, project["id"], project["user_id"]))

    for name, project_id, user_id in await resolve_name_only_links(report=report):
        try:
            linear_project_id = await fetch_linear_project_id(name=name)
        except (RuntimeError, LinearError) as error:
            report.failures.append(f"{name}: {error}")
            continue
        if not linear_project_id:
            print_message(f"No Linear project named {name} to sync", style="info")
            continue
        key = linear_project_id.lower()
        if key in walked:
            report.failures.append(f"{name}: the Linear project is already linked to {walked[key]}")
            continue
        walked[key] = project_id
        targets.append((linear_project_id, project_id, user_id))

    return targets


async def resolve_name_only_links(*, report: SyncReport) -> list[tuple[str, str, str]]:
    """Return the name-only links of the Demetra projects.

    Two Demetra projects can share a name, and the name is the only link to
    Linear for them. An ambiguous name is rejected, because the issues of the
    Linear project cannot be attributed to a single Demetra project.

    Args:
        report: The report the failures are recorded in.

    Returns:
        list[tuple[str, str, str]]: The project name and the project and user
            it belongs to.
    """
    by_name: dict[str, list[dict[str, str]]] = {}
    for project in await list_name_only_linear_projects():
        by_name.setdefault(project["name"].lower(), []).append(project)

    links: list[tuple[str, str, str]] = []
    for projects in by_name.values():
        if len(projects) > 1:
            report.failures.append(f"{projects[0]['name']}: {len(projects)} projects share this name")
            continue
        project = projects[0]
        links.append((project["name"], project["id"], project["user_id"]))
    return links


async def sync_linear_mirror(*, dry_run: bool = False) -> SyncReport:
    """Mirror every issue of the linked Linear projects into the local store.

    A project or an issue that cannot be read is recorded as a failure and the
    backfill continues, so a partial run keeps the results it already
    mirrored. Only the issues that were written are counted as mirrored.

    Args:
        dry_run: When True, the issues are counted but nothing is written.

    Returns:
        SyncReport: The counters of the run.
    """
    report = SyncReport()
    for linear_project_id, project_id, user_id in await resolve_sync_targets(report=report):
        report.projects += 1
        print_message(f"Syncing Linear project {linear_project_id}", style="info")
        try:
            issues = await fetch_project_issues(linear_project_id=linear_project_id)
        except (RuntimeError, LinearError) as error:
            report.failures.append(f"{linear_project_id}: {error}")
            continue
        for issue in issues:
            issue_id = issue.get("id")
            if not issue_id:
                continue
            try:
                comments = await fetch_issue_comments(issue_id=issue_id)
            except (RuntimeError, LinearError) as error:
                report.failures.append(f"{issue_id}: {error}")
                continue
            comment_count = len(extract_comment_rows(comments))
            if dry_run:
                report.pending_issues += 1
                report.pending_comments += comment_count
                continue
            payload = {**issue, "comments": {"nodes": comments}}
            try:
                await store_linear_issue(issue=payload, project_id=project_id, user_id=user_id)
            except SQLAlchemyError as error:
                report.failures.append(f"{issue_id}: {error}")
                continue
            report.issues += 1
            report.comments += comment_count
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
    issues = report.pending_issues if dry_run else report.issues
    comments = report.pending_comments if dry_run else report.comments
    print_message(
        f"{prefix}synced {issues} issues and {comments} comments from {report.projects} Linear projects",
        style="result",
    )
    for failure in report.failures:
        print_message(f"Failed: {failure}", style="error")
    return 1 if report.failures else 0
