from demetra.exceptions import InfiniteLoopError
from demetra.lint import run_linter
from demetra.models import Context
from demetra.review import run_review_agents
from demetra.services.flow import user_input
from demetra.services.opencode import opencode_build_agent
from demetra.services.tui import print_message
from demetra.settings import MAX_BUILD_ATTEMPTS


async def run_build_step(build_plan: str, context: Context) -> None:
    current_task: str = build_plan
    for _ in range(1, MAX_BUILD_ATTEMPTS + 1):
        print_message("Running BUILD agent", style="heading")
        await opencode_build_agent(
            target_path=context.worktree_path,
            task=current_task,
            session_id=context.session_id,
            task_title=context.linear_task.full_title,
        )

        print_message("Running CODE REVIEW agents", style="heading")
        review_comments = await run_review_agents(target_path=context.worktree_path, session_id=context.session_id)
        if review_comments:
            if context.auto_mode:
                current_task = review_comments
                continue

            result, _ = await user_input([("1", "approve"), ("2", "skip")])
            if result == "approve":
                print_message("Applying proposed changes.")
                current_task = review_comments
                continue
            else:
                print_message("Continuing the workflow.", style="result")

        has_errors, lint_result = await run_linter(target_path=context.worktree_path, session_id=context.session_id)
        if has_errors and lint_result:
            current_task = lint_result
            continue

        return

    raise InfiniteLoopError
