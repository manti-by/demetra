import asyncio
from pathlib import Path

from demetra.services.database import update_session_step
from demetra.services.groq import summarize_review
from demetra.services.opencode import opencode_review_agent
from demetra.services.tui import print_message
from demetra.services.utils import NO_ISSUE_TOKENS
from demetra.settings import OPENCODE


async def run_review_agents(
    target_path: Path, session_id: str | None = None, task_id: str | None = None, env: dict[str, str] | None = None
) -> str | None:
    print_message("Running REVIEW agents", style="heading")

    review_agents = []
    for model in OPENCODE["review_models"]:
        review_agents.append(opencode_review_agent(target_path=target_path, model=model, env=env))
    results = await asyncio.gather(*review_agents)

    if task_id:
        await update_session_step(task_id=task_id, step="review")

    parts = []
    for _, stdout, _ in results:
        if not stdout:
            continue
        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if any(stripped == token.strip() for token in NO_ISSUE_TOKENS):
                continue
            parts.append(stripped)
    review_output = "\n\n".join(parts)

    findings = await summarize_review(review_output=review_output)
    if findings:
        print_message("Review agents returned comments", style="result")
        findings_text = "\n".join(f"{i + 1}. {finding}" for i, finding in enumerate(findings))
        print_message(findings_text, style="result")
        return findings_text

    print_message("No comments from any review agent, continuing the workflow.", style="result")
    return None
