import argparse
import asyncio

from demetra.exceptions import DemetraError
from demetra.services.cursor import review_agent
from demetra.services.database import create_session, get_session, init_db
from demetra.services.filesystem import get_project_root
from demetra.services.flow import interruption
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push, git_worktree_create
from demetra.services.linear import get_linear_task, linear_cleanup, update_ticket_status
from demetra.services.opencode import build_agent, get_opencode_session_id, plan_agent
from demetra.services.precommit import run_ruff_checks, run_ty_checks
from demetra.services.test import check_pytest_support, run_tests
from demetra.services.tui import print_heading, print_message
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
        try:
            await update_ticket_status(task_id=task.id, state_id=LINEAR_STATE_IN_PROGRESS_ID)
        except DemetraError:
            print_message("Failed to update ticket status to In Progress", style="error")

        plan_output = None
        current_task: str = task.text
        while True:
            print_message("Running PLAN agent", style="heading")
            _, plan_output, _ = await plan_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )
            if not plan_output:
                print_message("Plan is empty, exiting the workflow.", style="error")
                return

            if session_id is None:
                if session_id := await get_opencode_session_id(target_path=worktree_path, task_title=task.full_title):
                    session = await create_session(task_id=task.id, session_id=session_id)

            print_message("Plan step is completed", style="heading")
            print_message(f"Plan output:\n{plan_output}")

            result, comment = interruption([("1", "approve"), ("2", "comment"), ("3", "exit")])
            if result == "exit":
                print_message("Cancelled, exiting the workflow.", style="error")
                return
            elif result == "comment" and comment:
                current_task = comment
                continue
            else:
                break

        current_task = plan_output
        while True:
            print_message("Running BUILD agent", style="heading")
            await build_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )

            print_message("Running CODE REVIEW agent", style="heading")
            _, review_comments, _ = await review_agent(target_path=worktree_path, session_id=session_id)
            if review_comments:
                result, _ = interruption([("1", "approve"), ("2", "skip")])
                if result == "approve":
                    print_message("Applying proposed changes.")
                    current_task = review_comments
                    continue
                else:
                    print_message("Continuing the workflow.", style="result")
            else:
                print_message("No comments from review agent, continuing the workflow.", style="result")

            print_message("Running linting checks", style="heading")
            ty_exit_code, ty_result, _ = await run_ty_checks(target_path=worktree_path, session_id=session_id)
            if ty_exit_code:
                print_message("Processing TY comments.", style="heading")
                current_task = ty_result
                continue

            ruff_exit_code, ruff_result, _ = await run_ruff_checks(target_path=worktree_path, session_id=session_id)
            if ruff_exit_code:
                print_message("Processing RUFF comments.", style="heading")
                current_task = ruff_result
                continue

            if await check_pytest_support(target_path=worktree_path):
                print_message("Running tests", style="heading")
                pytest_exit_code, pytest_result, _ = await run_tests(target_path=worktree_path, session_id=session_id)
                if pytest_exit_code:
                    print_message("Processing PYTEST errors.", style="heading")
                    current_task = pytest_result
                    continue

            break

        print_message("Commiting changes", style="heading")
        await git_add_all(target_path=worktree_path)
        await git_commit(target_path=worktree_path, message=task.full_title)

        print_message("Pushing changes", style="heading")
        await git_push(target_path=worktree_path)

        try:
            await update_ticket_status(task_id=task.id, state_id=LINEAR_STATE_IN_REVIEW_ID)
        except DemetraError:
            print_message("Failed to update ticket status to In Review", style="error")

        is_error = False
        print_message("Workflow complete", style="heading")
    finally:
        await git_cleanup(
            target_path=project_path, worktree_path=worktree_path, branch_name=branch_name, is_error=is_error
        )
        await linear_cleanup(task_id=task.id, is_error=is_error)


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(project_name=args.project_name))
