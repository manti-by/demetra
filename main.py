import argparse
import asyncio

from demetra.services.coderabbit import review_agent
from demetra.services.filesystem import get_project_root
from demetra.services.git import git_cleanup, git_commit, git_push, git_worktree_create
from demetra.services.linear import get_linear_task
from demetra.services.opencode import build_agent, plan_agent
from demetra.services.tui import print_heading, print_message


parser = argparse.ArgumentParser(prog="chimera", description="Run AI workflow.", add_help=True)
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
    try:
        repeat = False
        plan_output = None
        current_task = task.text
        while True:
            print_message("Running PLAN agent", style="heading")
            plan_output = await plan_agent(target_path=worktree_path, task=current_task, repeat=repeat)

            print_message("Plan step is completed", style="heading")
            print_message("Options: approve (default) | reject | comment")
            user_input = input("Action: ").strip().lower()

            if user_input == "reject":
                print_message("Rejected. Exiting.", style="error")
                return
            elif user_input == "comment":
                comment = input("Enter comment: ").strip()
                if comment:
                    task.comments.append(comment)
                    current_task = comment
                    repeat = True
                continue
            else:
                break

        while True:
            print_message("Running BUILD agent", style="heading")
            await build_agent(target_path=worktree_path, task=plan_output, repeat=True)

            print_message("Running CODE REVIEW agent", style="heading")
            review_comments = await review_agent(target_path=worktree_path)

            if not review_comments:
                print_message("No comments from review", style="result")
                break
            plan_output = review_comments

            print_message("Options: approve (default) | reject")
            user_input = input("Action: ").strip().lower()

            if user_input == "reject":
                print_message("Rejected. Exiting.")
                return
            elif user_input == "approve":
                continue

        print_message("Commiting changes", style="heading")
        await git_commit(target_path=worktree_path, message=f"{task.identifier}: {task.title}")

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
