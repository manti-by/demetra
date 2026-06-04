import asyncio
from pathlib import Path

from demetra.services.database import update_session_step
from demetra.services.opencode import opencode_review_agent
from demetra.services.tui import print_message
from demetra.services.utils import merge_review_results
from demetra.settings import OPENCODE


async def run_review_agents(target_path: Path, session_id: str | None = None, task_id: str | None = None) -> str | None:
    print_message("Running REVIEW agents", style="heading")

    review_agents = []
    for model in OPENCODE["review_models"]:
        review_agents.append(opencode_review_agent(target_path=target_path, model=model))
    results = await asyncio.gather(*review_agents)

    if task_id:
        await update_session_step(task_id=task_id, step="review")

    _, opencode_comments, _ = await merge_review_results(results=results)
    if opencode_comments:
        print_message("Review agents returned comments", style="result")
        print_message(opencode_comments, style="result")
        return opencode_comments

    print_message("No comments from any review agent, continuing the workflow.", style="result")
    return None
