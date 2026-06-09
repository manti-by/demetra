import argparse
import asyncio
import logging.config

from demetra.library.exceptions import AutoCancelledError, DemetraError, InfiniteLoopError, UserCancelledError
from demetra.services.database import init_db, mark_session_posted
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.tui import print_heading, print_message
from demetra.services.utils import setup_session_logging
from demetra.settings import DEFAULT_USER_ID, LINEAR, LOGGING, MAX_BUILD_ATTEMPTS
from demetra.workflows.build import run_build_step
from demetra.workflows.cleanup import cleanup_workflow, commit_and_push
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

    await setup_session_logging(logger=logger, task_id=context.linear_task.id)

    is_success = False
    should_update_linear_status = True
    try:
        await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["in_progress"])

        if not context.session or context.session.step == "initial":
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
        should_update_linear_status = False

    except DemetraError as e:
        print_message(f"Workflow error: {e}", style="error")

    except OSError as e:
        print_message(f"OS Error: {e}", style="error")

    except RuntimeError as e:
        print_message(f"Runtime Error: {e}", style="error")

    finally:
        # Only run cleanup if we successfully created a context (which means worktree was created)
        if context:
            await cleanup_workflow(
                context=context, is_success=is_success, should_update_linear_status=should_update_linear_status
            )


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(
        main(
            project_name=args.project_name,
            auto_mode=args.auto,
            plan_loop=args.plan_loop,
            task_id=args.task_id,
        )
    )
