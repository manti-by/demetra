import argparse
import asyncio

from demetra.services.coderabbit import review_agent
from demetra.services.filesystem import get_project_root
from demetra.services.git import git_commit_and_push, git_worktree_create, git_worktree_remove
from demetra.services.linear import get_linear_task
from demetra.services.opencode import build_agent, plan_agent


parser = argparse.ArgumentParser(prog="chimera", description="Run AI workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)


async def main(project_name: str):
    print("\n--- Running workflow ---\n")

    project_path = get_project_root(project_name=project_name)
    print(f"Project root: {project_path}")

    print("\n--- Retrieving latest linear task ---\n")
    task = await get_linear_task(project_name=project_name)
    if not task:
        print("No TODO tasks found")
        return
    print(f"Retrieved task: {task.identifier} - {task.title}")

    print("\n--- Creating feature worktree ---\n")
    branch_name = f"opencode/feature/{task.slug}"
    stdout, stderr, worktree_path = await git_worktree_create(target_path=project_path, branch_name=branch_name)
    print(stdout, stderr)
    print(f"Created worktree at: {worktree_path}")

    plan_output = None
    while True:
        print("\n--- Running PLAN agent ---\n")
        result = await plan_agent(target_path=worktree_path, task=task.text)
        print(*result)

        print("\n--- Plan step is completed ---\n")
        print("Options: approve (default) | reject | comment")
        user_input = input("Action: ").strip().lower()

        if user_input == "reject":
            print("Rejected. Exiting.")
            return
        elif user_input == "comment":
            comment = input("Enter comment: ").strip()
            if comment:
                task.comments.append(comment)
            continue
        else:
            plan_output = stderr
            break

    while True:
        print("\n--- Running BUILD agent ---\n")
        result = await build_agent(target_path=worktree_path, task=plan_output)
        print(*result)

        print("\n--- Running CODE REVIEW agent ---\n")
        stdout, stderr = await review_agent(target_path=worktree_path)
        print(stdout, stderr)

        if not stderr.strip():
            print("\n--- No comments from review ---\n")
            break
        plan_output = stderr

        print("\nOptions: approve (default) | reject")
        user_input = input("Action: ").strip().lower()

        if user_input == "reject":
            print("Rejected. Exiting.")
            return
        elif user_input == "approve":
            continue

    print("\n--- Commiting changes ---\n")
    result = await git_commit_and_push(target_path=worktree_path, message=f"{task.identifier}: {task.title}")
    print(*result)

    print("\n--- Removing worktree ---\n")
    result = await git_worktree_remove(target_path=project_path, worktree_path=worktree_path)
    print(*result)

    print("\n--- Workflow complete ---\n")


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(main(project_name=args.project_name))
