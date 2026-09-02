from demetra.library.exceptions import LinearError
from demetra.library.models import Context, LinearTask
from demetra.services.agents.opencode import (
    RESEARCH_HEADER_STRING,
    extract_research_report,
    opencode_research_agent,
)
from demetra.services.linear import get_linear_config_value, post_comment, update_ticket_status
from demetra.services.persistence.database import update_session_step
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
    """Run the research agent loop, post the report and move to Awaiting Input.

    Iterates the research agent up to ``MAX_RESEARCH_ATTEMPTS`` times,
    extracts the ``## Research Report`` section, posts it as a Linear comment,
    and moves the ticket to ``awaiting_input``.

    Args:
        context: The workflow context.

    Returns:
        str | None: The extracted research report, or None when no report
            could be produced after all attempts.

    Raises:
        LinearError: When the awaiting_input state is not configured or a
            Linear mutation (comment posting, status update) fails.
    """
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

        if not await post_comment(task_id=context.linear_task.id, body=report):
            raise LinearError("Failed to post research report to Linear")

        state_id = await get_linear_config_value(name="awaiting_input", user_id=context.project.user_id)
        if state_id is None:
            raise LinearError("Linear state 'awaiting_input' is not configured")
        if not await update_ticket_status(task_id=context.linear_task.id, state_id=state_id):
            raise LinearError("Failed to move ticket to Awaiting Input")
        await update_session_step(task_id=context.linear_task.id, step="awaiting_input")
        print_message("Task moved to Awaiting Input state.", style="result")
        return report

    if last_report is None:
        print_message("Research agent produced no report after all attempts.", style="error")
    return last_report
