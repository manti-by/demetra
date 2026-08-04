from demetra.library.models import Context
from demetra.services.opencode import opencode_resolve_agent
from demetra.services.prompt import get_prompt
from demetra.services.tui import print_message


async def run_resolve_step(context: Context, original_task: str, questions: list[str]) -> str:
    """Run the resolve agent to answer a task's open questions.

    Builds a numbered question prompt and returns the raw resolve agent
    output.

    Args:
        context: The workflow context.
        original_task: The original task description.
        questions: The open questions to resolve.

    Returns:
        str: The resolve agent output.
    """
    print_message("Running RESOLVE agent", style="heading")

    numbered_questions = "\n".join(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    task = await get_prompt(
        "resolve_questions",
        original_task=original_task,
        numbered_questions=numbered_questions,
    )

    _, resolve_output, _ = await opencode_resolve_agent(
        target_path=context.worktree_path,
        task=task,
        task_title=f"{context.linear_task.full_title} - resolve",
        env=context.project.environment,
    )

    print_message(f"Resolve agent output:\n{resolve_output}", style="info")
    return resolve_output
