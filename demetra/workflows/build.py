from demetra.library.exceptions import BuildError, InfiniteLoopError
from demetra.library.models import Context
from demetra.services.database import record_session_step_history, update_session_step
from demetra.services.flow import user_input
from demetra.services.opencode import opencode_build_agent
from demetra.services.project import bump_project_version, is_epic_label
from demetra.services.tui import print_message
from demetra.settings import CONTEXT_COMPACTION_THRESHOLD, MAX_BUILD_ATTEMPTS, MAX_REVIEW_ATTEMPTS
from demetra.workflows.lint import run_lint_and_test
from demetra.workflows.review import run_review_agents


async def check_and_compact_context(context: Context) -> None:
    """Check the opencode session length and run /compact if it exceeds the threshold.

    Also records the session length in session_history for the 'build' step.
    """
    if not context.session_id:
        return

    length = await get_opencode_session_length(
        target_path=context.worktree_path, session_id=context.session_id, env=context.project.environment
    )

    await record_session_step_history(
        target_path=context.worktree_path,
        session_id=context.session_id,
        step="build",
        env=context.project.environment,
    )

    if length is not None and length > CONTEXT_COMPACTION_THRESHOLD:
        print_message(
            f"Session length ({length:,} tokens) exceeds threshold ({CONTEXT_COMPACTION_THRESHOLD:,}), compacting.",
            style="info",
        )
        await opencode_compact_session(
            target_path=context.worktree_path, session_id=context.session_id, env=context.project.environment
        )


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

        await check_and_compact_context(context)

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
