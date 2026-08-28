import argparse
import asyncio
import logging.config
import sys

from demetra.library.exceptions import (
    AutoCancelledError,
    BuildError,
    DemetraError,
    InfiniteLoopError,
    LinearError,
    PullRequestError,
    ReviewError,
    UserCancelledError,
    WikiError,
)
from demetra.services.auth import reset_password_cli
from demetra.services.auth.allowlist import allowlist_cli
from demetra.services.auth.waitlist import waitlist_cli
from demetra.services.linear import get_linear_config_value, post_comment, update_ticket_status
from demetra.services.persistence.database import init_db, mark_session_posted, upsert_pending_session
from demetra.services.runtime.tui import print_heading, print_message
from demetra.services.runtime.utils import setup_session_logging
from demetra.settings import (
    DEFAULT_USER_ID,
    LOGGING,
    MAX_BUILD_ATTEMPTS,
)
from demetra.workflows.build import run_build_step
from demetra.workflows.cleanup import cleanup_workflow, commit_and_push
from demetra.workflows.failure import process_build_failure, process_pr_failure, process_wiki_failure
from demetra.workflows.plan import run_plan_step
from demetra.workflows.setup import setup_workflow


logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser(prog="demetra", description="Run implementation workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)
parser.add_argument("-t", "--task-id", help="Specific Linear task ID to run", type=str)
parser.add_argument(
    "--auto", help="Automatic mode - post questions and exit", action=argparse.BooleanOptionalAction, default=True
)
parser.add_argument(
    "--plan-loop",
    help="Loop between plan and resolve agents instead of posting questions to Linear",
    action=argparse.BooleanOptionalAction,
    default=False,
)
parser.add_argument(
    "--resetpass",
    help="Reset a user's password interactively",
    action="store_true",
)

parser.add_argument(
    "--allowlist",
    help="Allowlist management sub-action: add, remove, list, seed-existing",
    choices=["add", "remove", "list", "seed-existing"],
    default=None,
)
parser.add_argument("--type", help="Allowlist entry type (email or github_username)", default=None)
parser.add_argument("--value", help="Allowlist entry value", default=None)
parser.add_argument("--note", help="Optional note for the allowlist entry", default=None)
parser.add_argument("--dry-run", help="Report seed-existing counts without writing", action="store_true")

parser.add_argument(
    "--waitlist",
    help="Waitlist management sub-action: list, approve, remove",
    choices=["list", "approve", "remove"],
    default=None,
)
parser.add_argument("--waitlist-entry-id", help="Waitlist entry id for approve/remove", default=None)
parser.add_argument("--waitlist-status", help="Optional status filter for waitlist list", default=None)
parser.add_argument("--approved-by", help="Optional admin user id recorded on waitlist approve", default=None)


async def main(project_name: str, auto_mode: bool = True, plan_loop: bool = False, task_id: str | None = None):
    await init_db()
    await print_heading()

    print_message("Running workflow", style="heading")
    context = await setup_workflow(project_name=project_name, auto_mode=auto_mode, task_id=task_id)
    if not context:
        return

    context.plan_loop = plan_loop

    if not context.linear_task.user_id and DEFAULT_USER_ID:
        context.linear_task.user_id = DEFAULT_USER_ID

    await setup_session_logging(task_id=context.linear_task.id)

    is_success = False
    should_update_linear_status = True
    failure_step = "failed"
    try:
        if not context.session:
            context.session = await upsert_pending_session(
                task_id=context.linear_task.id,
                session_id=None,
                project_id=context.project.id,
                user_id=context.linear_task.user_id or DEFAULT_USER_ID,
                name=context.linear_task.full_title,
                linear_link=context.linear_task.url,
            )

        state_id = await get_linear_config_value(
            name="in_progress", user_id=context.linear_task.user_id or DEFAULT_USER_ID
        )
        if state_id is None:
            raise LinearError("Linear state 'in_progress' is not configured")
        await update_ticket_status(task_id=context.linear_task.id, state_id=state_id)

        if not context.session or not context.session.build_plan:
            if not await run_plan_step(context=context):
                return

        if not context.session:
            print_message("Empty session, exiting.", style="error")
            return

        if not context.session.build_plan:
            print_message("Empty build plan, exiting.", style="error")
            return

        if not context.session.posted_to_linear:
            if await post_comment(task_id=context.linear_task.id, body=context.session.build_plan):
                await mark_session_posted(task_id=context.linear_task.id)

        build_plan = context.session.build_plan
        commit_retries = MAX_BUILD_ATTEMPTS
        while commit_retries:
            await run_build_step(build_plan=build_plan, context=context)

            if await commit_and_push(context=context):
                break

            build_plan = (
                "The previous build attempt produced no staged changes. "
                "You MUST implement the required changes and stage them using `git add`.\n\n"
                f"Original plan:\n{build_plan}"
            )
            commit_retries -= 1
        else:
            raise InfiniteLoopError("Build agent repeatedly produced no changes")

        is_success = True

    except InfiniteLoopError:
        print_message("Infinite loop detected, exiting.", style="error")

    except UserCancelledError:
        print_message("User cancelled, exiting the workflow.", style="error")

    except AutoCancelledError:
        print_message("User cancelled, exiting the workflow.", style="error")
        failure_step, should_update_linear_status = "awaiting_input", False

    except PullRequestError as e:
        await process_pr_failure(context=context, error=e)
        failure_step, should_update_linear_status = "awaiting_input", False

    except ReviewError as e:
        await process_pr_failure(context=context, error=e)
        failure_step, should_update_linear_status = "awaiting_input", False

    except WikiError as e:
        await process_wiki_failure(context=context, error=e)
        failure_step, should_update_linear_status = "awaiting_input", False

    except BuildError as e:
        await process_build_failure(context=context, error=e)
        failure_step, should_update_linear_status = "awaiting_input", False

    except DemetraError as e:
        print_message(f"Workflow error: {e}", style="error")

    except ValueError as e:
        print_message(f"Configuration error: {e}", style="error")

    except OSError as e:
        print_message(f"OS Error: {e}", style="error")

    except RuntimeError as e:
        print_message(f"Runtime Error: {e}", style="error")

    finally:
        # Only run cleanup if we successfully created a context (which means worktree was created)
        if context:
            await cleanup_workflow(
                context=context,
                is_success=is_success,
                should_update_linear_status=should_update_linear_status,
                failure_step=failure_step,
            )


if __name__ == "__main__":
    args = parser.parse_args()

    if args.resetpass:
        sys.exit(asyncio.run(reset_password_cli()))
    elif args.allowlist:
        sys.exit(
            asyncio.run(
                allowlist_cli(
                    action=args.allowlist,
                    entry_type=args.type,
                    value=args.value,
                    note=args.note,
                    dry_run=args.dry_run,
                )
            )
        )
    elif args.waitlist:
        sys.exit(
            asyncio.run(
                waitlist_cli(
                    action=args.waitlist,
                    entry_id=args.waitlist_entry_id,
                    status=args.waitlist_status,
                    approved_by=args.approved_by,
                )
            )
        )
    else:
        asyncio.run(
            main(
                project_name=args.project_name,
                auto_mode=args.auto,
                plan_loop=args.plan_loop,
                task_id=args.task_id,
            )
        )
