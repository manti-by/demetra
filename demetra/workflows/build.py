from demetra.library.exceptions import BuildError, InfiniteLoopError
from demetra.library.models import Context
from demetra.services.agents.opencode import (
    capture_agent_session,
    get_opencode_session_tokens,
    opencode_build_agent,
    opencode_compact_session,
    opencode_supports_compaction,
)
from demetra.services.persistence.database import update_session_step
from demetra.services.runtime.flow import user_input
from demetra.services.runtime.project import bump_project_version
from demetra.services.runtime.tui import print_message
from demetra.settings import CONTEXT_COMPACTION_THRESHOLD, MAX_ATTEMPTS
from demetra.workflows.lint import run_lint_and_test
from demetra.workflows.review import run_review_agents
from demetra.workflows.validate import run_validate_agent


async def check_and_compact_context(context: Context, context_tokens: int | None = None) -> None:
    """Compact the build session when its context snapshot exceeds the threshold.

    ``context_tokens`` is the gauge recorded on the build invocation row (the
    last assistant turn's ``input + cache.read``). When this opencode version has
    no ``run --command`` there is no CLI compaction path, so the fork-once build
    design is documented and reported as the only context bound instead of
    silently paying for a full-context turn that changes nothing. When
    compaction does run, the session is re-exported so the measured context is
    confirmed to have shrunk.

    Args:
        context: The workflow context with the active session.
        context_tokens: The recorded context snapshot, or None when unavailable.
    """
    if context.session_id is None or context_tokens is None:
        return
    if context_tokens <= CONTEXT_COMPACTION_THRESHOLD:
        return

    if not await opencode_supports_compaction(target_path=context.worktree_path, environment=context.environment):
        print_message(
            f"Context size ({context_tokens:,} tokens) exceeds threshold ({CONTEXT_COMPACTION_THRESHOLD:,}) "
            "but this opencode version has no compaction command; the fork-once build session bounds context.",
            style="warning",
        )
        return

    print_message(
        f"Context size ({context_tokens:,} tokens) exceeds threshold ({CONTEXT_COMPACTION_THRESHOLD:,}), compacting.",
        style="info",
    )
    compact_exit_code, _, compact_stderr = await opencode_compact_session(
        target_path=context.worktree_path, session_id=context.session_id, environment=context.environment
    )
    if compact_exit_code != 0:
        print_message(f"Failed to compact session: {compact_stderr.strip()}", style="error")
        return

    usage = await get_opencode_session_tokens(
        target_path=context.worktree_path,
        session_id=context.session_id,
        environment=context.environment,
    )
    if usage is None or usage.context is None:
        return
    if usage.context >= context_tokens:
        print_message(
            f"Compaction did not reduce context ({usage.context:,} tokens, was {context_tokens:,}); "
            "the fork-once build session remains the only context bound.",
            style="warning",
        )
        return
    print_message(f"Context size after compaction: {usage.context:,} tokens.", style="info")


async def run_build_step(build_plan: str, context: Context) -> None:
    """Run the build, validate, review, version bump and lint/test loop.

    Iterates the build agent, feeding it missing plan items, review comments or
    lint/test failures as the next task until the pipeline is clean or the
    attempt budget is exhausted. The first invocation forks the plan session
    once; every later iteration resumes the fork so the context is bounded
    exactly once. The validate agent checks the staged diff for plan coverage
    before the review agents run; the project version is bumped once after the
    first clean pass.

    Args:
        build_plan: The plan to feed the build agent on the first iteration.
        context: The workflow context.

    Raises:
        BuildError: When the build or validate agent exits with an error.
        InfiniteLoopError: When the attempt budget is exhausted.
    """
    current_task: str = build_plan
    rerun_attempts = MAX_ATTEMPTS["build"]
    validate_attempts = MAX_ATTEMPTS["build"]
    review_attempts = MAX_ATTEMPTS["review"]
    is_version_updated = False
    review_step_finished = False
    is_first_build = True
    review_round = 0
    while rerun_attempts:
        print_message("Running BUILD agent", style="heading")
        await update_session_step(task_id=context.linear_task.id, step="build")

        fork = is_first_build and context.session_id is not None
        exit_code, stdout, stderr = await opencode_build_agent(
            target_path=context.worktree_path,
            task=current_task,
            session_id=context.session_id,
            task_title=context.linear_task.full_title,
            project_id=context.project.id,
            environment=context.environment,
            fork=fork,
        )
        if exit_code != 0:
            raise BuildError(
                f"Build agent failed (exit {exit_code}): {stderr.strip() or stdout.strip() or 'unknown error'}"
            )

        history = await capture_agent_session(
            task_id=context.linear_task.id,
            step="build",
            target_path=context.worktree_path,
            task_title=context.linear_task.full_title,
            session_id=context.session_id,
            forked=fork,
            is_primary=is_first_build,
            environment=context.environment,
        )
        if forked_session_id := (history.session_id if history is not None else None):
            if context.session is not None:
                context.session.session_id = forked_session_id
        context_tokens = history.context_tokens if history is not None else None
        is_first_build = False

        await check_and_compact_context(context, context_tokens)

        if review_attempts > 0 and validate_attempts > 0 and not review_step_finished:
            await update_session_step(task_id=context.linear_task.id, step="validate")
            missing_items = await run_validate_agent(
                target_path=context.worktree_path,
                build_plan=build_plan,
                task_title=context.linear_task.full_title,
                task_id=context.linear_task.id,
                project_id=context.project.id,
                environment=context.environment,
            )
            if missing_items:
                if context.auto_mode:
                    current_task = missing_items
                    rerun_attempts -= 1
                    validate_attempts -= 1
                    continue

                result, _ = await user_input(options=[("1", "apply missing plan items"), ("2", "skip")])
                if result == "apply missing plan items":
                    print_message(message="Applying missing plan items.")
                    current_task = missing_items
                    rerun_attempts -= 1
                    validate_attempts -= 1
                    continue
                else:
                    print_message("Continuing the workflow.", style="result")
                    rerun_attempts = MAX_ATTEMPTS["build"]
                    validate_attempts = MAX_ATTEMPTS["build"]
                    review_attempts = MAX_ATTEMPTS["review"]

            await update_session_step(task_id=context.linear_task.id, step="review")
            review_round += 1
            review_comments = await run_review_agents(
                target_path=context.worktree_path,
                task_id=context.linear_task.id,
                task_title=context.linear_task.full_title,
                round_index=review_round,
                project_id=context.project.id,
                environment=context.environment,
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
                    rerun_attempts = MAX_ATTEMPTS["build"]
                    validate_attempts = MAX_ATTEMPTS["build"]
                    review_attempts = MAX_ATTEMPTS["review"]
        else:
            print_message("Skipping CODE REVIEW (attempt budget reached)", style="warning")

        review_step_finished = True

        if not is_version_updated:
            new_version = bump_project_version(target_path=context.worktree_path)
            print_message(f"Updated project version to {new_version}", style="info")
            is_version_updated = True

        has_errors, lint_result = await run_lint_and_test(
            target_path=context.worktree_path,
            session_id=context.session_id,
            task_id=context.linear_task.id,
            environment=context.environment,
        )
        if has_errors and lint_result:
            current_task = lint_result
            rerun_attempts -= 1
            continue
        return

    raise InfiniteLoopError
