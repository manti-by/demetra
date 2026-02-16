import argparse
import asyncio

from demetra.exceptions import DemetraError
from demetra.services.cursor import review_agent
from demetra.services.database import create_session, get_session, init_db
from demetra.services.filesystem import get_project_root
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push, git_worktree_create
from demetra.services.linear import get_linear_task, linear_cleanup, update_ticket_status
from demetra.services.opencode import build_agent, get_opencode_session_id, plan_agent
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
        current_task = task.text
        while True:
            print_message("Running PLAN agent", style="heading")
            plan_output = await plan_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )

            if session_id is None:
                if session_id := await get_opencode_session_id(target_path=worktree_path, task_title=task.full_title):
                    session = await create_session(task_id=task.id, session_id=session_id)

            print_message("Plan step is completed", style="heading")
            print_message(f"Plan output:\n{plan_output}")

            print_message("How would you like to proceed?")
            print_message("  [1] approve - default")
            print_message("  [2] comment")
            print_message("  [3] exit")

            while True:
                user_input = input("Action: ").strip().lower()
                if user_input in ["1", "2", "3", "approve", "comment", "exit"]:
                    break
                print_message("Invalid choice. Please try again.")

            if user_input in ["3", "exit"]:
                print_message("Cancelled, exiting the workflow.", style="error")
                return

            elif user_input in ["2", "comment"]:
                comment = input("Enter comment: ").strip()
                if comment:
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
            review_comments = await review_agent(target_path=worktree_path, session_id=session_id)
            if not review_comments:
                print_message("No comments from review agent, continuing the workflow.", style="result")
                break

            print_message("How would you like to proceed?")
            print_message("  [1] approve (apply comments) - default")
            print_message("  [2] skip (go to next task)")

            while True:
                user_input = input("Action: ").strip().lower()
                if user_input in ["1", "2", "approve", "skip"]:
                    break
                print_message("Invalid choice. Please try again.")

            if user_input in ["2", "skip"]:
                print_message("Continuing the workflow.", style="result")
                break

            else:
                print_message("Applying proposed changes.")
                current_task = review_comments
                continue

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
