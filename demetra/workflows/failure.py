from demetra.library.exceptions import LinearError, PullRequestError
from demetra.library.models import Context
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.runtime.template import get_template
from demetra.services.runtime.tui import print_message
from demetra.settings import LINEAR


async def process_pr_failure(context: Context, error: PullRequestError) -> None:
    """Handle a pull request creation failure: notify Linear and set recovery state.

    The build, commit and push steps already succeeded, so the branch lives on
    the remote. Posts a Linear comment with the branch, a manual compare URL and
    the error, then moves the ticket to ``Awaiting Input``. Linear API failures
    and failed status updates surface a manual-recovery message instead of
    failing silently, since cleanup will not move the ticket afterwards.

    Args:
        context: The workflow context.
        error: The pull request creation error.
    """
    print_message(f"Pull request creation failed: {error}", style="error")
    body = await get_template(
        "pr_creation_failed",
        branch_name=context.branch_name,
        repository_owner=context.project.repository_owner,
        repository_name=context.project.repository_name,
        error=error,
    )
    try:
        comment_posted = await post_comment(task_id=context.linear_task.id, body=body)
        status_updated = await update_ticket_status(
            task_id=context.linear_task.id, state_id=LINEAR["states"]["awaiting_input"]
        )
    except LinearError as e:
        print_message(
            f"Failed to update Linear after PR creation failure: {e}. Move the ticket to Awaiting Input manually.",
            style="error",
        )
    else:
        if not comment_posted:
            print_message("Failed to post PR-creation-failure comment to Linear", style="error")
        if not status_updated:
            print_message(
                "Failed to move the ticket to Awaiting Input in Linear; move it manually.",
                style="error",
            )
