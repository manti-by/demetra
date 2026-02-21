import argparse
import asyncio

from demetra.exceptions import DemetraError, InfiniteLoopError
from demetra.services.cursor import review_agent
from demetra.services.database import create_session, get_session, init_db
from demetra.services.filesystem import get_project_root
from demetra.services.flow import user_input
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push, git_worktree_create
from demetra.services.github import create_pull_request
from demetra.services.linear import get_linear_task, linear_cleanup, post_comment, update_ticket_status
from demetra.services.lint import run_ruff_checks, run_ruff_format
from demetra.services.opencode import build_agent, extract_plan, get_opencode_session_id, plan_agent
from demetra.services.test import run_pytests
from demetra.services.tui import print_heading, print_message
from demetra.services.utils import is_package_installed
from demetra.settings import LINEAR_STATE_IN_PROGRESS_ID, LINEAR_STATE_IN_REVIEW_ID


parser = argparse.ArgumentParser(prog="demetra", description="Run implementation workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)


async def main(project_name: str):
    await init_db()
    await print_heading()

    print_message("Running workflow", style="heading")

    project_path = get_project_root(project_name=project_name)
    print_message(f"Project root: {project_path}", style="result")

    print_message("Retrieving latest linear task", style="heading")
    task = await get_linear_task(project_name=project_name)
    if not task:
        print_message("No TODO tasks found", style="error")
        return
    print_message(f"Retrieved task: {task.identifier} - {task.title}", style="result")

    print_message("Creating feature worktree", style="heading")
    print_message("")
    branch_name = f"opencode/feature/{task.slug}"
    worktree_path = await git_worktree_create(target_path=project_path, branch_name=branch_name)
    print_message("")
    print_message(f"Created worktree at: {worktree_path}", style="result")

    is_error = True
    session = await get_session(task_id=task.id)
    session_id = session.session_id if session else None
    try:
        await update_ticket_status(task_id=task.id, state_id=LINEAR_STATE_IN_PROGRESS_ID)

        plan_output = None
        current_task: str = task.text
        while True:
            print_message("Running PLAN agent", style="heading")
            _, plan_output, _ = await plan_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )

            build_plan = await extract_plan(plan_output=plan_output)
            if not build_plan:
                print_message("Plan is empty, exiting the workflow.", style="error")
                return

            if session_id is None:
                if session_id := await get_opencode_session_id(target_path=worktree_path, task_title=task.full_title):
                    session = await create_session(task_id=task.id, session_id=session_id)

            print_message("Plan step is completed", style="heading")
            print_message(f"Plan output:\n{build_plan}")

            result, comment = await user_input([("1", "approve"), ("2", "comment"), ("3", "exit")])
            if result == "exit":
                print_message("Cancelled, exiting the workflow.", style="error")
                return
            elif result == "comment" and comment:
                current_task = comment
                continue
            else:
                break

        print_message("Posting build plan to Linear ticket", style="heading")
        await post_comment(task_id=task.id, body=build_plan)

        current_task = build_plan
        for build_attempt in range(3):
            build_attempt += 1
            if build_attempt == 3:
                raise InfiniteLoopError

            print_message("Running BUILD agent", style="heading")
            await build_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )

            print_message("Running CODE REVIEW agent", style="heading")
            _, review_comments, _ = await review_agent(target_path=worktree_path, session_id=session_id)
            if review_comments:
                result, _ = await user_input([("1", "approve"), ("2", "skip")])
                if result == "approve":
                    print_message("Applying proposed changes.")
                    current_task = review_comments
                    continue
                else:
                    print_message("Continuing the workflow.", style="result")
            else:
                print_message("No comments from review agent, continuing the workflow.", style="result")

            if await is_package_installed(target_path=worktree_path, package_name="ruff"):
                print_message("Running RUFF linter", style="heading")
                await run_ruff_format(target_path=worktree_path, session_id=session_id)

                ruff_exit_code, ruff_result, _ = await run_ruff_checks(target_path=worktree_path, session_id=session_id)
                if ruff_exit_code:
                    print_message("Processing RUFF comments.", style="result")
                    current_task = ruff_result
                    continue

            if await is_package_installed(target_path=worktree_path, package_name="pytest"):
                print_message("Running PYTESTs", style="heading")
                pytest_exit_code, pytest_result, _ = await run_pytests(target_path=worktree_path, session_id=session_id)
                if pytest_exit_code:
                    print_message("Processing PYTEST errors.", style="result")
                    current_task = pytest_result
                    continue

            break

        print_message("Committing changes", style="heading")
        await git_add_all(target_path=worktree_path)
        await git_commit(target_path=worktree_path, message=task.full_title)

        print_message("Pushing changes", style="heading")
        await git_push(target_path=worktree_path, branch_name=branch_name)

        print_message("Creating GitHub PR", style="heading")
        await create_pull_request(target_path=worktree_path, branch_name=branch_name, title=task.full_title)

        try:
            await update_ticket_status(task_id=task.id, state_id=LINEAR_STATE_IN_REVIEW_ID)
        except DemetraError:
            print_message("Failed to update ticket status to In Review", style="error")

        is_error = False
        print_message("Workflow complete", style="heading")

    except InfiniteLoopError:
        print_message("Infinite loop detected, exiting.", style="error")

    except DemetraError:
        print_message("Failed to update ticket status to In Progress", style="error")

    except OSError as e:
        print_message(f"OS Error: {e}", style="error")

    finally:
        await git_cleanup(
            target_path=project_path, worktree_path=worktree_path, branch_name=branch_name, is_error=is_error
        )
        await linear_cleanup(task_id=task.id, is_error=is_error)


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(project_name=args.project_name))
