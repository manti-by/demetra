import argparse
import asyncio

from demetra.build import run_build_step
from demetra.cleanup import cleanup_workflow, commit_and_push
from demetra.exceptions import DemetraError, InfiniteLoopError, UserCancelledError
from demetra.plan import run_plan_step
from demetra.services.database import get_session, init_db, mark_build_plan_posted, save_build_plan
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

    success = False
    try:
        await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR_STATE_IN_PROGRESS_ID)

        if context.build_plan and context.build_plan.plan_content:
            build_plan = context.build_plan.plan_content
            print_message("Using existing build plan from database", style="heading")
        else:
            build_plan = await run_plan_step(context=context)
            if build_plan is None:
                return

            await save_build_plan(task_id=context.linear_task.id, plan_content=build_plan)

        if context.session_id is None and (session := await get_session(task_id=context.linear_task.id)):
            context.session = session

        if not context.build_plan or not context.build_plan.posted_to_linear:
            try:
                await post_comment(task_id=context.linear_task.id, body=build_plan)
                await mark_build_plan_posted(task_id=context.linear_task.id)
            except (OSError, ValueError) as e:
                print_message(f"Warning: Failed to post comment or update DB: {e}", style="error")

        await run_build_step(build_plan=build_plan, context=context)

        await commit_and_push(context=context)
        success = True

    except InfiniteLoopError:
        print_message("Infinite loop detected, exiting.", style="error")

    except UserCancelledError:
        print_message("User cancelled, exiting the workflow.", style="error")

    except DemetraError as e:
        print_message(f"Workflow error: {e}", style="error")

    except OSError as e:
        print_message(f"OS Error: {e}", style="error")

    finally:
        await cleanup_workflow(context=context, success=success)


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(
        main(
            project_name=args.project_name,
            auto_mode=args.auto,
        )
    )
