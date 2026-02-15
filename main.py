import argparse
import asyncio

from demetra.services.cursor import review_agent
from demetra.services.database import create_session, get_session
from demetra.services.filesystem import get_project_root
from demetra.services.git import git_add_all, git_cleanup, git_commit, git_push, git_worktree_create
from demetra.services.linear import get_linear_task
from demetra.services.opencode import build_agent, get_opencode_session_id, plan_agent
from demetra.services.tui import print_heading, print_message


parser = argparse.ArgumentParser(prog="demetra", description="Run implementation workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)


async def main(project_name: str):
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
    branch_name = f"opencode/feature/{task.slug}"
    worktree_path = await git_worktree_create(target_path=project_path, branch_name=branch_name)
    print_message(f"Created worktree at: {worktree_path}", style="result")

    is_error = True
    session = get_session(task_id=task.id)
    session_id = session.session_id if session else None
    try:
        plan_output = None
        current_task = task.text
        while True:
            print_message("Running PLAN agent", style="heading")
            plan_output = await plan_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )

            if session_id is None:
                if session_id := await get_opencode_session_id(target_path=worktree_path, task_title=task.full_title):
                    session = create_session(task_id=task.id, session_id=session_id)

            print_message("Plan step is completed", style="heading")
            print_message(f"Plan output:\n{plan_output}")

            print_message("Options: approve - default | comment | exit")
            user_input = input("Action: ").strip().lower()

            if user_input == "exit":
                print_message("Cancelled, exiting the workflow.", style="error")
                return

            elif user_input == "comment":
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

            print_message("Options: approve (apply comments) - default | continue")
            user_input = input("Action: ").strip().lower()

            if user_input == "continue":
                print_message("Continuing the workflow.", style="result")
                break

            elif user_input == "approve":
                print_message("Applying proposed changes.")
                current_task = review_comments
                continue

        print_message("Commiting changes", style="heading")
        await git_add_all(target_path=worktree_path)
        await git_commit(target_path=worktree_path, message=task.full_title)

        print_message("Pushing changes", style="heading")
        await git_push(target_path=worktree_path)

        is_error = False
        print_message("Workflow complete", style="heading")
    finally:
        await git_cleanup(
            target_path=project_path, worktree_path=worktree_path, branch_name=branch_name, is_error=is_error
        )


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(project_name=args.project_name))
