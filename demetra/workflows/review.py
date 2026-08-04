import asyncio
from pathlib import Path

from demetra.services.groq import summarize_review
from demetra.services.opencode import opencode_review_agent
from demetra.services.tui import print_message
from demetra.services.utils import NO_ISSUE_TOKENS_CASE
from demetra.settings import OPENCODE


def filter_meaningful_reviews(findings: list[str]) -> list[str]:
    """Keep only review findings substantial enough to act on.

    Drops short strings and no-issue tokens.

    Args:
        findings: The review findings to filter.

    Returns:
        list[str]: The meaningful findings.
    """
    return [f for f in findings if len(f) >= 10 and f.casefold() not in NO_ISSUE_TOKENS_CASE]


async def run_review_agents(
    target_path: Path, session_id: str | None = None, task_id: str | None = None, env: dict[str, str] | None = None
) -> str | None:
    """Run all configured review agents in parallel and summarize their output.

    Gathers review agent outputs, filters no-issue lines, summarizes them via
    the LLM and keeps only meaningful findings.

    Args:
        target_path: Directory to run the reviews in.
        session_id: Reserved; not used by the review agents.
        task_id: Reserved; not used by the review agents.
        env: Optional environment overrides for the subprocess.

    Returns:
        str | None: The numbered review comments, or None when there are none.
    """
    print_message("Running REVIEW agents", style="heading")

    review_agents = []
    for model in OPENCODE["review_models"]:
        review_agents.append(opencode_review_agent(target_path=target_path, model=model, env=env))
    results = await asyncio.gather(*review_agents)

    parts = []
    for _, stdout, _ in results:
        if not stdout:
            continue
        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.casefold() in NO_ISSUE_TOKENS_CASE:
                continue
            parts.append(stripped)
    review_output = "\n\n".join(parts)

    findings = await summarize_review(review_output=review_output)
    if findings:
        meaningful = filter_meaningful_reviews(findings)
        if meaningful:
            print_message("Review agents returned comments", style="result")
            findings_text = "\n".join(f"{i + 1}. {finding}" for i, finding in enumerate(meaningful))
            print_message(findings_text, style="result")
            return findings_text

    print_message("No comments from any review agent, continuing the workflow.", style="result")
    return None
