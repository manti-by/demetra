from demetra.exceptions import AutoCancelledError, UserCancelledError
from demetra.models import Context
from demetra.services.database import save_session
from demetra.services.flow import user_input
from demetra.services.groq import extract_questions
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.opencode import extract_plan, get_opencode_session_id, opencode_plan_agent
from demetra.services.tui import print_message
from demetra.settings import LINEAR


async def run_plan_step(context: Context) -> str | None:
    plan_output = None
    current_task: str = context.linear_task.text
    while True:
        print_message("Running PLAN agent", style="heading")
        _, plan_output, _ = await opencode_plan_agent(
            target_path=context.worktree_path,
            task=current_task,
            session_id=context.session_id,
            task_title=context.linear_task.full_title,
        )

        build_plan = await extract_plan(plan_output=plan_output)
        if not build_plan:
            print_message("Plan is empty, exiting the workflow.", style="error")
            return None

        if context.session_id is None:
            if session_id := await get_opencode_session_id(
                target_path=context.worktree_path, task_title=context.linear_task.full_title
            ):
                context.session = await save_session(
                    task_id=context.linear_task.id, session_id=session_id, build_plan=build_plan
                )

        print_message("Plan step is completed", style="heading")
        print_message(f"Plan output:\n{build_plan}")

        questions = await extract_questions(plan_output=plan_output)
        if not questions:
            print_message("Plan is ready, proceeding to build automatically.", style="heading")
            return build_plan

        print_message(f"Questions detected:\n{questions}", style="heading")

        if context.auto_mode:
            print_message("Auto mode: posting questions to Linear and exiting.", style="heading")
            await post_comment(task_id=context.linear_task.id, body=f"## Questions:\n- {'\n- '.join(questions)}")

            await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["awaiting_input"])
            print_message("Task moved to Awaiting Input state.", style="result")

            raise AutoCancelledError

        print_message("Waiting for user input.", style="heading")

        result, comment = await user_input([("1", "approve"), ("2", "comment"), ("3", "exit")])
        if result == "exit":
            print_message("Cancelled, exiting the workflow.", style="error")
            raise UserCancelledError

        elif result == "comment" and comment:
            current_task = comment
            continue

        return build_plan
