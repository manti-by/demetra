import argparse
import asyncio

from demetra.build import run_build_step
from demetra.cleanup import cleanup_workflow, commit_and_push
from demetra.exceptions import AutoCancelledError, DemetraError, InfiniteLoopError, UserCancelledError
from demetra.plan import run_plan_step
from demetra.services.database import init_db, mark_session_posted
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.tui import print_heading, print_message
from demetra.settings import LINEAR_STATE_IN_PROGRESS_ID
from demetra.setup import setup_workflow


parser = argparse.ArgumentParser(prog="demetra", description="Run implementation workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)
parser.add_argument(
    "--auto", help="Automatic mode - post questions and exit", action=argparse.BooleanOptionalAction, default=True
)


async def main(project_name: str, auto_mode: bool = True):
    await init_db()
    await print_heading()

    print_message("Running workflow", style="heading")
    if not (context := await setup_workflow(project_name=project_name, auto_mode=auto_mode)):
        print_message("No TODO tasks found", style="error")
        return

    is_success = False
    should_update_linear_status = True
    try:
        await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR_STATE_IN_PROGRESS_ID)

        if not context.session:
            if not (build_plan := await run_plan_step(context=context)):
                return

        if context.session and not context.session.posted_to_linear:
            if await post_comment(task_id=context.linear_task.id, body=build_plan):
                await mark_session_posted(task_id=context.linear_task.id)

        await run_build_step(build_plan=build_plan, context=context)

        await commit_and_push(context=context)
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

    finally:
        await cleanup_workflow(
            context=context, is_success=is_success, should_update_linear_status=should_update_linear_status
        )


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(
        main(
            project_name=args.project_name,
            auto_mode=args.auto,
        )
    )
