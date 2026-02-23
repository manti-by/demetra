from pathlib import Path

from demetra.services.database import create_session, get_session
from demetra.services.flow import user_input
from demetra.services.opencode import (
    PLAN_HAS_QUESTIONS,
    PLAN_IS_READY_STRING,
    extract_plan,
    extract_questions,
    get_opencode_session_id,
    opencode_plan_agent,
)
from demetra.services.tui import print_message
from demetra.settings import LINEAR_STATE_AWAITING_INPUT_ID


async def run_plan_agent(
    target_path: Path,
    task_id: str,
    task: str,
    task_title: str,
    auto_mode: bool,
    session_id: str | None = None,
) -> tuple[str | None, bool]:
    session = await get_session(task_id=task_id)
    session_id = session.session_id if session else None

    plan_output = None
    current_task: str = task
    while True:
        print_message("Running PLAN agent", style="heading")
        _, plan_output, _ = await opencode_plan_agent(
            target_path=target_path, task=current_task, session_id=session_id, task_title=task_title
        )

        build_plan = await extract_plan(plan_output=plan_output)
        if not build_plan:
            print_message("Plan is empty, exiting the workflow.", style="error")
            return None, False

        if session_id is None:
            if session_id := await get_opencode_session_id(target_path=target_path, task_title=task_title):
                session = await create_session(task_id=task_id, session_id=session_id)

        print_message("Plan step is completed", style="heading")
        print_message(f"Plan output:\n{build_plan}")

        if PLAN_IS_READY_STRING in plan_output:
            print_message("Plan is ready, proceeding to build automatically.", style="heading")
            return build_plan, False
        elif PLAN_HAS_QUESTIONS in plan_output:
            questions = await extract_questions(plan_output=plan_output, build_plan=build_plan)
            print_message(f"Questions detected:\n{questions}", style="heading")

            if auto_mode:
                print_message("Auto mode: posting questions to Linear and exiting.", style="heading")
                from demetra.services.linear import post_comment, update_ticket_status

                await post_comment(task_id=task_id, body=f"## Questions\n{questions}")
                await update_ticket_status(task_id=task_id, state_id=LINEAR_STATE_AWAITING_INPUT_ID)
                print_message("Task moved to Awaiting Input state.", style="result")
                return None, True

            print_message("Waiting for user input.", style="heading")

        result, comment = await user_input([("1", "approve"), ("2", "comment"), ("3", "exit")])
        if result == "exit":
            print_message("Cancelled, exiting the workflow.", style="error")
            return None, False
        elif result == "comment" and comment:
            current_task = comment
            continue
        else:
            return build_plan, False
