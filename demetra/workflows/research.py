from typing import Any

from demetra.library.exceptions import EnvironmentConfigError, LinearConfigError, LinearError
from demetra.library.models import Context, LinearTask
from demetra.services.agents.opencode import (
    RESEARCH_HEADER_STRING,
    extract_research_report,
    opencode_research_agent,
)
from demetra.services.linear import create_issue_relation, create_research_ticket, update_ticket_status
from demetra.services.persistence.database import (
    update_session_research_report,
    update_session_step,
)
from demetra.services.runtime.tui import print_message
from demetra.settings import LINEAR, MAX_ATTEMPTS


def is_research_task(linear_task: LinearTask) -> bool:
    """Return whether a Linear task carries a research label.

    Compares the task's labels against the configured research labels
    case-insensitively.

    Args:
        linear_task: The Linear task to inspect.

    Returns:
        bool: True when at least one label matches a research label.
    """
    research_labels = {label.casefold() for label in LINEAR["research_labels"]}
    task_labels = {label.casefold() for label in linear_task.labels}
    return bool(research_labels & task_labels)


def is_research_ticket(context: Context) -> bool:
    """Return whether the ticket carries a research label.

    Args:
        context: The workflow context with the linear task.

    Returns:
        bool: True when at least one label matches a research label.
    """
    return is_research_task(linear_task=context.linear_task)


async def _validate_research_ticket_prerequisites(context: Context) -> None:
    """Fail fast when the related research ticket cannot be created.

    Checks the permanent prerequisites (source project, ``prd`` state,
    ``team_id`` and ``in_review`` state) before the research agent runs,
    so a misconfigured workspace does not burn ``MAX_ATTEMPTS["research"]`` LLM
    calls on a retry that can never succeed.

    Args:
        context: The workflow context with the originating Linear task.

    Raises:
        LinearConfigError: When the source project, the PRD state, the team id
            or the in-review state is not configured.
    """
    if not context.linear_task.linear_project_id:
        raise LinearConfigError("Source Linear task has no project to attach the research ticket to")
    try:
        context.environment.linear_state("prd")
    except EnvironmentConfigError as e:
        raise LinearConfigError("Linear state 'prd' is not configured") from e
    try:
        context.environment.linear_value("team_id")
    except EnvironmentConfigError as e:
        raise LinearConfigError("Linear team id is not configured") from e
    try:
        context.environment.linear_state("in_review")
    except EnvironmentConfigError as e:
        raise LinearConfigError("Linear state 'in_review' is not configured") from e


async def _run_research_agent(context: Context) -> str | None:
    """Run the research agent until it returns a report or the budget runs out.

    Args:
        context: The workflow context.

    Returns:
        str | None: The extracted research report, or None when no report could
            be produced after ``MAX_ATTEMPTS["research"]`` attempts.
    """
    attempts = MAX_ATTEMPTS["research"]
    while attempts > 0:
        print_message("Running RESEARCH agent", style="heading")
        await update_session_step(task_id=context.linear_task.id, step="research", session_id=context.session_id)

        exit_code, stdout, stderr = await opencode_research_agent(
            target_path=context.worktree_path,
            task=context.linear_task.text,
            task_title=context.linear_task.full_title,
            project_id=context.project.id,
            environment=context.environment,
        )
        if exit_code != 0:
            print_message(f"Research agent failed (exit {exit_code}): {(stderr or stdout).strip()}", style="error")
            attempts -= 1
            continue

        research_output = stdout.strip()
        print_message(f"Research agent output:\n{research_output}", style="info")

        if not research_output:
            print_message("Research agent produced no output, retrying.", style="warning")
            attempts -= 1
            continue

        if RESEARCH_HEADER_STRING not in research_output:
            print_message("Research output missing report header, retrying.", style="warning")
            attempts -= 1
            continue

        report = await extract_research_report(research_output=research_output)
        if not report:
            print_message("Extracted research report is empty, retrying.", style="warning")
            attempts -= 1
            continue

        print_message(f"Research report:\n{report}")
        try:
            persisted = await update_session_research_report(task_id=context.linear_task.id, research_report=report)
            if not persisted:
                print_message(
                    "Failed to persist research report: no session matched task_id, continuing.", style="warning"
                )
        except Exception:  # noqa: BLE001
            print_message("Failed to persist research report, continuing.", style="warning")
        return report

    return None


async def _create_research_ticket(context: Context, report: str) -> dict[str, Any] | None:
    """Create the related research ticket, retrying transient Linear failures.

    Uses its own retry budget so a flaky research agent cannot starve the
    Linear retries, and never re-runs the agent.

    Args:
        context: The workflow context.
        report: The research report to store as the ticket description.

    Returns:
        dict[str, Any] | None: The created ticket, or None when Linear kept
            failing after ``MAX_ATTEMPTS["research"]`` attempts.

    Raises:
        LinearConfigError: When Linear permanently rejects the ticket.
    """
    attempts = MAX_ATTEMPTS["research"]
    while attempts > 0:
        try:
            created_ticket = await create_research_ticket(context=context, report=report)
        except LinearConfigError:
            raise
        except LinearError as e:
            print_message(f"Failed to create research ticket: {e}, retrying.", style="warning")
            attempts -= 1
            continue

        if created_ticket.get("identifier"):
            return created_ticket
        print_message("Research ticket creation returned no identifier, retrying.", style="warning")
        attempts -= 1
    return None


async def _link_research_ticket(context: Context, research_ticket_id: str) -> None:
    """Relate the research ticket to the originating ticket, retrying failures.

    Linking is part of the deliverable, so a transient failure is retried with
    its own budget. A relation is idempotent in Linear: re-running the step
    after a lost response re-creates the same ``related`` relation instead of
    duplicating it.

    Args:
        context: The workflow context with the originating Linear task.
        research_ticket_id: The id of the created research ticket.

    Raises:
        LinearError: When the relation could not be created after all attempts.
    """
    attempts = MAX_ATTEMPTS["research"]
    while attempts > 0:
        try:
            linked = await create_issue_relation(task_id=context.linear_task.id, related_task_id=research_ticket_id)
        except LinearError as e:
            print_message(f"Failed to link research ticket: {e}, retrying.", style="warning")
            attempts -= 1
            continue

        if linked:
            return
        print_message("Linking the research ticket returned no success, retrying.", style="warning")
        attempts -= 1
    raise LinearError("Failed to link research ticket to the originating ticket after all attempts")


async def _move_to_in_review(context: Context) -> None:
    """Move the originating ticket to In Review and mark the step researched.

    The related ticket already exists by the time this runs, so a failure to
    move the source ticket is reported but not treated as a step failure.

    Args:
        context: The workflow context.
    """
    try:
        state_id = context.environment.linear_state("in_review")
    except EnvironmentConfigError:
        print_message("Linear state 'in_review' is not configured; move the ticket manually.", style="warning")
        return

    try:
        moved = await update_ticket_status(task_id=context.linear_task.id, state_id=state_id)
    except LinearError as e:
        print_message(f"Failed to move the ticket to In Review: {e}; move it manually.", style="warning")
        return

    if not moved:
        print_message("Failed to move the ticket to In Review in Linear; move it manually.", style="warning")
        return

    await update_session_step(task_id=context.linear_task.id, step="researched", session_id=context.session_id)
    print_message("Task moved to In Review state.", style="result")


async def run_research_step(context: Context) -> str | None:
    """Run the research agent, link a related ticket and move the task to In Review.

    Runs the research agent (retrying up to ``MAX_ATTEMPTS["research"]`` times)
    until it produces a ``## Research Report``, then creates a related Linear
    ticket with the report as its description, links it back to the originating
    ticket as ``related`` and moves the originating ticket to In Review, marking
    the session step ``researched``. Transient Linear failures are retried with a
    separate budget. Permanent configuration errors fail before the agent runs. A
    failure to move the originating ticket after the research ticket exists is
    reported but does not discard the deliverable.

    Args:
        context: The workflow context.

    Returns:
        str | None: The extracted research report, or None when no report
            could be produced after all attempts.

    Raises:
        LinearConfigError: When the research ticket prerequisites are missing
            or Linear permanently rejects the ticket.
        LinearError: When the research ticket could not be created, or the
            relation to the originating ticket could not be created, after all
            attempts.
    """
    await _validate_research_ticket_prerequisites(context=context)

    report = await _run_research_agent(context=context)
    if report is None:
        print_message("Research agent produced no report after all attempts.", style="error")
        return None

    created_ticket = await _create_research_ticket(context=context, report=report)
    if created_ticket is None:
        raise LinearError("Failed to create research ticket after all attempts")
    print_message(f"Created research ticket {created_ticket['identifier']}.", style="result")

    await _link_research_ticket(context=context, research_ticket_id=created_ticket["ticket_id"])

    await _move_to_in_review(context=context)
    return report
