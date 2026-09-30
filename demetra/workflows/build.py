from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import BuildError, InfiniteLoopError
from demetra.library.models import Context
from demetra.services.agents import harness
from demetra.services.persistence.database import record_session_step_history, update_session_step
from demetra.services.runtime.flow import user_input
from demetra.services.runtime.project import bump_project_version
from demetra.services.runtime.tui import print_message
from demetra.settings import CONTEXT_COMPACTION_THRESHOLD, MAX_ATTEMPTS
from demetra.workflows.lint import run_lint_and_test
from demetra.workflows.review import run_review_agents
from demetra.workflows.validate import run_validate_agent


async def check_and_compact_context(context: Context, session_id: str | None) -> None:
    """Check the session context and run /compact if it exceeds the threshold.

    Also records the full TokenUsage breakdown (input, output, reasoning,
    cache, and context tokens) along with the model in session_history for the
    ``build`` step. Token usage is read from ``session_id`` (the session the
    build agent actually ran under) but the history row is keyed by the
    persisted ``context.session_id`` so it stays attached to the session that
    ``sessions.session_id`` and the history API refer to.

    Args:
        context: The workflow context with the active session.
        session_id: The session id the build agent actually ran under (see
            :func:`run_build_step` for why this can differ from
            ``context.session_id`` on Claude).
    """
    if not session_id:
        return

    try:
        usage = await harness.get_session_tokens(
            target_path=context.worktree_path,
            session_id=session_id,
            environment=context.environment,
            env=context.project.environment,
        )
        history = await record_session_step_history(
            session_id=context.session_id or session_id,
            step="build",
            usage=usage,
            model=context.environment.agent_model("build"),
        )
    except (SQLAlchemyError, OSError):
        history = None
    context_tokens = history.context_tokens if history is not None else None

    if context_tokens is not None and context_tokens > CONTEXT_COMPACTION_THRESHOLD:
        print_message(
            f"Context size ({context_tokens:,} tokens) exceeds threshold ({CONTEXT_COMPACTION_THRESHOLD:,}), compacting.",
            style="info",
        )
        compact_exit_code, _, compact_stderr = await harness.compact_session(
            target_path=context.worktree_path,
            session_id=session_id,
            environment=context.environment,
            env=context.project.environment,
        )
        if compact_exit_code != 0:
            print_message(f"Failed to compact session: {compact_stderr.strip()}", style="error")


async def run_build_step(build_plan: str, context: Context) -> None:
    """Run the build, validate, review, version bump and lint/test loop.

    Iterates the build agent, feeding it missing plan items, review comments or
    lint/test failures as the next task until the pipeline is clean or the
    attempt budget is exhausted. The validate agent checks the staged diff for
    plan coverage before the review agents run; the project version is bumped
    once after the first clean pass.

    Args:
        build_plan: The plan to feed the build agent on the first iteration.
        context: The workflow context.

    Raises:
        BuildError: When the build or validate agent exits with an error.
        InfiniteLoopError: When the attempt budget is exhausted.
    """
    # Claude cannot resume the plan agent's session under a different --agent
    # (its system prompt is snapshotted on the first turn and reused verbatim
    # on every later request/resume, verified against the installed CLI) — so
    # the build step runs under its own fresh session for this run instead of
    # continuing the plan's. harness.new_session_id returns None for OpenCode,
    # which keeps resuming the plan session exactly as before. Every iteration
    # of the loop below reuses this same id under the same "build-agent", so
    # resuming across iterations stays safe. This id is never persisted: it is
    # scoped to build execution and token lookup only, so context.session_id
    # (sessions.session_id) stays the canonical, plan-linked id throughout —
    # a process restart simply starts a fresh build session, which is fine
    # since only conversational memory is lost, not the build plan or state.
    build_session_id = harness.new_session_id(environment=context.environment) or context.session_id

    current_task: str = build_plan
    rerun_attempts = MAX_ATTEMPTS["build"]
    validate_attempts = MAX_ATTEMPTS["build"]
    review_attempts = MAX_ATTEMPTS["review"]
    is_version_updated = False
    review_step_finished = False
    while rerun_attempts:
        print_message("Running BUILD agent", style="heading")
        await update_session_step(task_id=context.linear_task.id, step="build")

        exit_code, stdout, stderr = await harness.build_agent(
            target_path=context.worktree_path,
            task=current_task,
            environment=context.environment,
            session_id=build_session_id,
            task_title=context.linear_task.full_title,
            env=context.project.environment,
            project_id=context.project.id,
        )
        if exit_code != 0:
            raise BuildError(
                f"Build agent failed (exit {exit_code}): {stderr.strip() or stdout.strip() or 'unknown error'}"
            )

        await check_and_compact_context(context, session_id=build_session_id)

        if review_attempts > 0 and validate_attempts > 0 and not review_step_finished:
            await update_session_step(task_id=context.linear_task.id, step="validate")
            missing_items = await run_validate_agent(
                target_path=context.worktree_path,
                build_plan=build_plan,
                env=context.project.environment,
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
            review_comments = await run_review_agents(
                target_path=context.worktree_path,
                session_id=context.session_id,
                task_id=context.linear_task.id,
                env=context.project.environment,
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
            env=context.project.environment,
        )
        if has_errors and lint_result:
            current_task = lint_result
            rerun_attempts -= 1
            continue
        return

    raise InfiniteLoopError
