from demetra.library.exceptions import BuildError, InfiniteLoopError
from demetra.library.models import Context
from demetra.services.database import update_session_step
from demetra.services.flow import user_input
from demetra.services.opencode import opencode_build_agent
from demetra.services.project import bump_project_version, is_epic_label
from demetra.services.tui import print_message
from demetra.settings import MAX_BUILD_ATTEMPTS, MAX_REVIEW_ATTEMPTS
from demetra.workflows.lint import run_lint_and_test
from demetra.workflows.review import run_review_agents


async def run_build_step(build_plan: str, context: Context) -> None:
    current_task: str = build_plan
    rerun_attempts = MAX_BUILD_ATTEMPTS
    review_attempts = MAX_REVIEW_ATTEMPTS
    is_version_updated = False
    review_step_finished = False
    while rerun_attempts:
        print_message("Running BUILD agent", style="heading")
        await update_session_step(task_id=context.linear_task.id, step="build")

        exit_code, stdout, stderr = await opencode_build_agent(
            target_path=context.worktree_path,
            task=current_task,
            session_id=context.session_id,
            task_title=context.linear_task.full_title,
            env=context.project.environment,
        )
        if exit_code != 0:
            raise BuildError(
                f"Build agent failed (exit {exit_code}): {stderr.strip() or stdout.strip() or 'unknown error'}"
            )

        if review_attempts > 0 and not review_step_finished:
            await update_session_step(task_id=context.linear_task.id, step="review")
            review_comments = await run_review_agents(
                target_path=context.worktree_path, session_id=context.session_id, env=context.project.environment
            )
            if review_comments:
                if context.auto_mode:
                    current_task = review_comments
                    rerun_attempts -= 1
                    review_attempts -= 1
                    continue

                result, _ = await user_input([("1", "apply review comments"), ("2", "skip")])
                if result == "apply review comments":
                    print_message("Applying proposed changes.")
                    current_task = review_comments
                    rerun_attempts -= 1
                    review_attempts -= 1
                    continue
                else:
                    print_message("Continuing the workflow.", style="result")
                    rerun_attempts = MAX_BUILD_ATTEMPTS
                    review_attempts = MAX_REVIEW_ATTEMPTS
        else:
            print_message("Skipping CODE REVIEW (MAX_REVIEW_ATTEMPTS reached)", style="warning")

        review_step_finished = True

        if not is_version_updated:
            new_version = bump_project_version(
                target_path=context.worktree_path,
                is_epic=is_epic_label(labels=context.linear_task.labels),
            )
            print_message(f"Updated project version to {new_version}", style="info")
            is_version_updated = True

        has_errors, lint_result = await run_lint_and_test(
            target_path=context.worktree_path,
            session_id=context.session_id,
            task_id=context.linear_task.id,
            env=context.project.environment,
        )
        if has_errors and lint_result:
            current_task = lint_result
            rerun_attempts -= 1
            continue
        return

    raise InfiniteLoopError
