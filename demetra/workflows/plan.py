from sqlalchemy.exc import SQLAlchemyError

from demetra.library.exceptions import AutoCancelledError, InfiniteLoopError, PlanError, UserCancelledError
from demetra.library.models import Context
from demetra.services.database import record_session_step_history, save_session, update_session_step
from demetra.services.flow import user_input
from demetra.services.groq import extract_plan, extract_questions
from demetra.services.linear import post_comment, update_ticket_status
from demetra.services.opencode import get_opencode_session_id, get_opencode_session_tokens, opencode_plan_agent
from demetra.services.tui import print_message
from demetra.services.utils import NO_ISSUE_TOKENS
from demetra.settings import LINEAR, MAX_PLAN_ATTEMPTS, OPENCODE
from demetra.workflows.resolve import run_resolve_step


async def run_plan_step(context: Context) -> str | None:
    """Run the plan agent and finalize a build plan for the task.

    Iterates the plan agent, extracts and saves the build plan, records
    session token history, and resolves open questions either automatically
    (plan loop / resolve agent), via Linear comments, or through user input.

    Args:
        context: The workflow context.

    Returns:
        str | None: The finalized build plan, or None when the plan is empty.

    Raises:
        PlanError: When the plan agent exits with an error.
        AutoCancelledError: In auto mode when questions are posted to Linear.
        UserCancelledError: When the user exits the workflow.
        InfiniteLoopError: When the plan loop attempt budget is exhausted.
    """
    current_task: str = context.linear_task.text
    plan_attempts = MAX_PLAN_ATTEMPTS if context.plan_loop else 1
    while plan_attempts > 0:
        print_message("Running PLAN agent", style="heading")
        await update_session_step(task_id=context.linear_task.id, step="plan")

        exit_code, stdout, stderr = await opencode_plan_agent(
            target_path=context.worktree_path,
            task=current_task,
            task_title=context.linear_task.full_title,
            env=context.project.environment,
        )
        if exit_code != 0:
            raise PlanError(
                f"Plan agent failed (exit {exit_code}): {(stderr or '').strip() or (stdout or '').strip() or 'unknown error'}"
            )

        plan_output = stdout
        print_message(f"Plain plan agent output:\n{plan_output}", style="info")

        build_plan = await extract_plan(
            plan_output=plan_output.strip(),
            task_description=context.linear_task.description,
            comments=context.linear_task.comments,
        )
        if not build_plan:
            print_message("Plan is empty, exiting the workflow.", style="error")
            return None

        print_message(
            f"Searching session for {context.linear_task.full_title} / {context.worktree_path}", style="heading"
        )

        session_id = None
        if not context.session_id:
            session_id = await get_opencode_session_id(
                target_path=context.worktree_path,
                task_title=context.linear_task.full_title,
                env=context.project.environment,
            )
        if session_id:
            context.session = await save_session(
                task_id=context.linear_task.id,
                session_id=session_id,
                build_plan=build_plan,
                name=context.linear_task.full_title,
                linear_link=context.linear_task.url,
            )
            print_message(f"Saved session {session_id}.", style="result")
        else:
            context.session = await save_session(
                task_id=context.linear_task.id, build_plan=build_plan, linear_link=context.linear_task.url
            )
            print_message("No opencode session found, saved build plan without session_id.", style="warning")

        print_message("Plan step is completed", style="heading")
        print_message(f"Plan output:\n{build_plan}")

        if context.session_id:
            try:
                usage = await get_opencode_session_tokens(
                    target_path=context.worktree_path,
                    session_id=context.session_id,
                    env=context.project.environment,
                )
                await record_session_step_history(
                    session_id=context.session_id,
                    step="plan",
                    usage=usage,
                    model=OPENCODE["plan_model"],
                )
            except (SQLAlchemyError, OSError):
                print_message("Failed to record session step history.", style="warning")

        questions = await extract_questions(plan_output=plan_output)
        questions = [q for q in questions if q.lower() not in NO_ISSUE_TOKENS and "no output" not in q.lower()]
        if not questions:
            print_message("Plan is ready, proceeding to build automatically.", style="heading")
            return build_plan

        print_message(f"Questions detected:\n{questions}", style="heading")

        if context.plan_loop and context.auto_mode:
            plan_attempts -= 1
            if plan_attempts <= 0:
                print_message("Plan loop attempts exhausted, exiting the workflow.", style="error")
                raise InfiniteLoopError

            print_message(
                f"Plan loop enabled, sending questions to RESOLVE agent (attempts left: {plan_attempts}).",
                style="heading",
            )
            resolve_output = await run_resolve_step(
                context=context, original_task=context.linear_task.text, questions=questions
            )
            current_task = (
                f"Original Task:\n{context.linear_task.text}\n\n"
                f"Resolved Answers:\n{resolve_output}\n\n"
                "Revisit your plan with these resolved answers, finalize it, "
                "and re-emit the Implementation Plan section."
            )
            continue

        if context.auto_mode:
            print_message("Auto mode: posting questions to Linear and exiting.", style="heading")
            for question in questions:
                if not await post_comment(task_id=context.linear_task.id, body=f"## Question:\n{question}"):
                    print_message("Failed to post question to Linear", style="error")

            await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["awaiting_input"])
            await update_session_step(task_id=context.linear_task.id, step="awaiting_input")
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
