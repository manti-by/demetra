from demetra.library.exceptions import LinearError
from demetra.library.models import Context, LinearTask
from demetra.services.agents.opencode import (
    RESEARCH_HEADER_STRING,
    extract_research_report,
    opencode_research_agent,
)
from demetra.services.linear import (
    create_issue_relation,
    create_linear_ticket,
    get_linear_config_value,
    update_ticket_status,
)
from demetra.services.persistence.database import update_session_research_ticket_id, update_session_step
from demetra.services.runtime.tui import print_message
from demetra.settings import LINEAR, MAX_RESEARCH_ATTEMPTS


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


async def run_research_step(context: Context) -> str | None:
    """Run the research agent loop, create a related ticket and move to In Review.

    Iterates the research agent up to ``MAX_RESEARCH_ATTEMPTS`` times,
    extracts the ``## Research Report`` section, creates a new Linear ticket
    carrying the report, links it to the source ticket as related, and moves
    the source ticket to ``in_review``.

    The created ticket id is persisted on the session and reused on a re-run,
    so a transient failure after creation cannot mint a duplicate.

    Args:
        context: The workflow context.

    Returns:
        str | None: The extracted research report, or None when no report
            could be produced after all attempts.

    Raises:
        LinearError: When ticket creation, relation creation, the in_review
            state lookup or a Linear status mutation fails.
        RuntimeError: When the context has no session, since the created
            ticket id must be persisted for the step to be idempotent.
    """
    session = context.session
    if session is None:
        raise RuntimeError("Research step requires a session")

    attempts = MAX_RESEARCH_ATTEMPTS
    last_report: str | None = None
    while attempts > 0:
        print_message("Running RESEARCH agent", style="heading")
        await update_session_step(task_id=context.linear_task.id, step="research")

        exit_code, stdout, stderr = await opencode_research_agent(
            target_path=context.worktree_path,
            task=context.linear_task.text,
            task_title=context.linear_task.full_title,
            env=context.project.environment,
            project_id=context.project.id,
            user_environment=context.project.user_environment,
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

        last_report = report
        print_message(f"Research report:\n{report}")

        research_ticket_id = session.research_ticket_id
        if research_ticket_id is None:
            related_title = f"Research: {context.linear_task.identifier} - {context.linear_task.title}"
            try:
                created = await create_linear_ticket(
                    title=related_title,
                    description=report,
                    technical_requirements="",
                    acceptance_criteria="",
                    user_id=context.project.user_id,
                )
            except LinearError as e:
                raise LinearError("Failed to create research ticket") from e
            research_ticket_id = created["ticket_id"]
            await update_session_research_ticket_id(
                task_id=context.linear_task.id, research_ticket_id=research_ticket_id
            )

        if not await create_issue_relation(task_id=context.linear_task.id, related_task_id=research_ticket_id):
            raise LinearError("Failed to link research ticket to source ticket")

        state_id = await get_linear_config_value(name="in_review", user_id=context.project.user_id)
        if state_id is None:
            raise LinearError("Linear state 'in_review' is not configured")
        if not await update_ticket_status(task_id=context.linear_task.id, state_id=state_id):
            raise LinearError("Failed to move ticket to In Review")
        await update_session_step(task_id=context.linear_task.id, step="researched")
        print_message("Research ticket created and linked, task moved to In Review.", style="result")
        return report

    if last_report is None:
        print_message("Research agent produced no report after all attempts.", style="error")
    return last_report
