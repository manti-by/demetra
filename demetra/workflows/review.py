import asyncio
from pathlib import Path

from demetra.library.models import SessionEnvironment
from demetra.services.agents.opencode import capture_agent_session, opencode_review_agent
from demetra.services.llm.openrouter import summarize_review
from demetra.services.runtime.tui import print_message
from demetra.services.runtime.utils import NO_ISSUE_TOKENS_CASE
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
    target_path: Path,
    *,
    task_id: str | None = None,
    task_title: str | None = None,
    round_index: int = 0,
    project_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> str | None:
    """Run all configured review agents in parallel and summarize their output.

    Each review agent runs in its own session with a title unique to the round
    and model, so every run is attributed as its own ``review`` invocation row
    (one per round and model). Gathers the outputs, filters no-issue lines,
    summarizes them via the LLM and keeps only meaningful findings.

    Args:
        target_path: Directory to run the reviews in.
        task_id: Optional task id used to record each review invocation.
        task_title: Optional session title base, suffixed per model.
        round_index: The 1-based build review round, used in the title.
        project_id: Optional project id used for OS env opt-in tokens.
        environment: The resolved session environment, forwarded to the review
            agents, used to resolve their models and to configure the LLM
            summarizer.

    Returns:
        str | None: The numbered review comments, or None when there are none.

    Raises:
        ReviewError: When the LLM review summarization fails.
    """
    print_message("Running REVIEW agents", style="heading")

    models = environment.review_models if environment is not None else OPENCODE["review_models"]
    base_title = task_title or "review"
    titles = [f"{base_title} - review r{round_index} {model}" for model in models]
    review_agents = [
        opencode_review_agent(
            target_path=target_path,
            model=model,
            task_title=title,
            environment=environment,
            project_id=project_id,
        )
        for model, title in zip(models, titles, strict=True)
    ]
    results = await asyncio.gather(*review_agents)

    for title in titles:
        await capture_agent_session(
            task_id=task_id,
            step="review",
            target_path=target_path,
            task_title=title,
            environment=environment,
        )

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

    findings = await summarize_review(review_output=review_output, environment=environment)
    if findings:
        meaningful = filter_meaningful_reviews(findings)
        if meaningful:
            print_message("Review agents returned comments", style="result")
            findings_text = "\n".join(f"{i + 1}. {finding}" for i, finding in enumerate(meaningful))
            print_message(findings_text, style="result")
            return findings_text

    print_message("No comments from any review agent, continuing the workflow.", style="result")
    return None
