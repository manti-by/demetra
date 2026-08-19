from demetra.library.exceptions import DemetraError, LinearError, ReviewError
from demetra.library.models import Context
from demetra.services.linear import get_linear_config_value, post_comment, update_ticket_status
from demetra.services.runtime.template import get_template
from demetra.services.runtime.tui import print_message


async def process_pr_failure(context: Context, error: DemetraError) -> None:
    """Handle a workflow failure: notify Linear and set recovery state.

    Posts a Linear comment describing the failure and moves the ticket to
    ``Awaiting Input``. For a pull request creation failure the branch already
    lives on the remote, so the comment includes the branch and a manual
    compare URL; for a review summarization failure it reports the error. Linear
    API failures and failed status updates surface a manual-recovery message
    instead of failing silently, since cleanup will not move the ticket.

    Args:
        context: The workflow context.
        error: The pull request creation or review summarization error.
    """
    if isinstance(error, ReviewError):
        print_message(f"Review summarization failed: {error}", style="error")
        body = await get_template("review_failed", error=error)
        comment_label = "review-failure"
    else:
        print_message(f"Pull request creation failed: {error}", style="error")
        body = await get_template(
            "pr_creation_failed",
            branch_name=context.branch_name,
            repository_owner=context.project.repository_owner,
            repository_name=context.project.repository_name,
            error=error,
        )
        comment_label = "PR-creation-failure"
    try:
        comment_posted = await post_comment(task_id=context.linear_task.id, body=body)
        state_id = await get_linear_config_value(name="awaiting_input", user_id=context.project.user_id)
        if state_id is None:
            raise LinearError("Linear state 'awaiting_input' is not configured")
        status_updated = await update_ticket_status(task_id=context.linear_task.id, state_id=state_id)
    except LinearError as e:
        print_message(
            f"Failed to update Linear after failure: {e}. Move the ticket to Awaiting Input manually.",
            style="error",
        )
    else:
        if not comment_posted:
            print_message(f"Failed to post {comment_label} comment to Linear", style="error")
        if not status_updated:
            print_message(
                "Failed to move the ticket to Awaiting Input in Linear; move it manually.",
                style="error",
            )
