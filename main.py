import argparse
import asyncio

from demetra.build import run_build_agent
from demetra.exceptions import DemetraError, InfiniteLoopError
from demetra.finalize import cleanup, commit_and_push, create_pr
from demetra.linear import get_linear_task, linear_cleanup, post_comment, update_ticket_status
from demetra.lint import run_linter
from demetra.plan import run_plan_agent
from demetra.review import run_review_agents
from demetra.services.database import get_session, init_db
from demetra.services.filesystem import get_project_root
from demetra.services.tui import print_heading, print_message
from demetra.settings import LINEAR_STATE_IN_PROGRESS_ID, LINEAR_STATE_IN_REVIEW_ID


parser = argparse.ArgumentParser(prog="demetra", description="Run implementation workflow.", add_help=True)
parser.add_argument("-p", "--project-name", help="Project name to run workflow on", type=str)
parser.add_argument(
    "--auto", help="Automatic mode - post questions and exit", action=argparse.BooleanOptionalAction, default=True
)


async def main(project_name: str, auto_mode: bool = True):
    await init_db()
    await print_heading()

    print_message("Running workflow", style="heading")

    project_path = get_project_root(project_name=project_name)
    print_message(f"Project root: {project_path}", style="result")

    task = await get_linear_task(project_name=project_name)
    if not task:
        return

    from demetra.worktree import create_worktree

    branch_name = f"opencode/feature/{task.slug}"
    worktree_path, _ = await create_worktree(target_path=project_path, branch_name=branch_name)

    is_error = True
    session = await get_session(task_id=task.id)
    session_id = session.session_id if session else None

    try:
        await update_ticket_status(task_id=task.id, state_id=LINEAR_STATE_IN_PROGRESS_ID)

        build_plan, should_exit = await run_plan_agent(
            target_path=worktree_path,
            task_id=task.id,
            task=task.text,
            task_title=task.full_title,
            auto_mode=auto_mode,
            session_id=session_id,
        )
        if should_exit or build_plan is None:
            return
        assert build_plan is not None

        if session_id is None:
            session = await get_session(task_id=task.id)
            session_id = session.session_id if session else None

        await post_comment(task_id=task.id, body=build_plan)

        current_task: str = build_plan
        for build_attempt in range(3):
            build_attempt += 1
            if build_attempt == 3:
                raise InfiniteLoopError

            print_message("Running BUILD agent", style="heading")
            await run_build_agent(
                target_path=worktree_path, task=current_task, session_id=session_id, task_title=task.full_title
            )

            print_message("Running CODE REVIEW agents", style="heading")
            review_comments = await run_review_agents(target_path=worktree_path, session_id=session_id)
            if review_comments:
                if auto_mode:
                    current_task = review_comments
                    continue

                from demetra.services.flow import user_input

                result, _ = await user_input([("1", "approve"), ("2", "skip")])
                if result == "approve":
                    print_message("Applying proposed changes.")
                    current_task = review_comments
                    continue
                else:
                    print_message("Continuing the workflow.", style="result")
            else:
                print_message("There are no review comments, continuing the workflow.", style="result")

            has_errors, lint_result = await run_linter(target_path=worktree_path, session_id=session_id)
            if has_errors and lint_result:
                current_task = lint_result
                continue

            break

        await commit_and_push(target_path=worktree_path, branch_name=branch_name, title=task.full_title)

        await create_pr(target_path=worktree_path, branch_name=branch_name, title=task.full_title)

        is_error = False
        print_message("Workflow complete", style="heading")

        await update_ticket_status(task_id=task.id, state_id=LINEAR_STATE_IN_REVIEW_ID)

    except InfiniteLoopError:
        print_message("Infinite loop detected, exiting.", style="error")

    except DemetraError:
        print_message("Failed to update ticket status", style="error")

    except OSError as e:
        print_message(f"OS Error: {e}", style="error")

    finally:
        await cleanup(
            project_path=project_path, worktree_path=worktree_path, branch_name=branch_name, is_error=is_error
        )
        await linear_cleanup(task_id=task.id, is_error=is_error)


if __name__ == "__main__":
    args = parser.parse_args()
    asyncio.run(
        main(
            project_name=args.project_name,
            auto_mode=args.auto,
        )
    )
