from demetra.library.exceptions import InfiniteLoopError
from demetra.library.models import Context
from demetra.services.flow import user_input
from demetra.services.opencode import opencode_build_agent
from demetra.services.tui import print_message
from demetra.settings import MAX_BUILD_ATTEMPTS, MAX_REVIEW_ATTEMPTS
from demetra.workflows.lint import run_linter
from demetra.workflows.review import run_review_agents


async def run_build_step(build_plan: str, context: Context) -> None:
    current_task: str = build_plan
    rerun_attempts = MAX_BUILD_ATTEMPTS
    review_attempts = MAX_REVIEW_ATTEMPTS
    while rerun_attempts:
        print_message("Running BUILD agent", style="heading")
        await opencode_build_agent(
            target_path=context.worktree_path,
            task=current_task,
            session_id=context.session_id,
            task_title=context.linear_task.full_title,
        )

        if review_attempts > 0:
            print_message("Running CODE REVIEW agents", style="heading")
            review_comments = await run_review_agents(target_path=context.worktree_path, session_id=context.session_id)
            if review_comments:
                if context.auto_mode:
                    current_task = review_comments
                    rerun_attempts -= 1
                    review_attempts -= 1
                    continue

                result, _ = await user_input([("1", "approve"), ("2", "skip")])
                if result == "approve":
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

        has_errors, lint_result = await run_linter(target_path=context.worktree_path, session_id=context.session_id)
        if has_errors and lint_result:
            current_task = lint_result
            rerun_attempts -= 1
            continue

        return

    raise InfiniteLoopError
