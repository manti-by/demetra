import logging
from pathlib import Path

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.exc import SQLAlchemyError

from demetra.library.constants import WIKI_REQUIRED_SECTIONS
from demetra.library.exceptions import EnvironmentConfigError, PlanError, PrDescriptionError, ReviewError, WikiError
from demetra.library.models import SessionEnvironment, TokenUsage
from demetra.services.llm.factory import build_llm, resolve_llm_model
from demetra.services.llm.parser import NumberedListOutputParser
from demetra.services.llm.prompt import get_prompt
from demetra.services.persistence.database import record_llm_call
from demetra.services.runtime.utils import non_negative_int


logger = logging.getLogger(__name__)


PLAN_OUTPUT_MAX_CHARS = 32_000

TICKET_FIELDS = ("title", "description", "technical_requirements", "acceptance_criteria", "project_name")


def _exclusive(total: object, detail: object) -> int:
    """Return the counter tokens outside a reported detail subset.

    OpenAI-compatible payloads report ``prompt_tokens``/``completion_tokens``
    *including* their cached and reasoning subsets, while :class:`TokenUsage`
    keeps disjoint counters (the opencode ``info.tokens`` convention). The
    detail is therefore subtracted from the total so a call's tokens are never
    counted twice.

    Args:
        total: The reported total counter.
        detail: The reported subset already contained in ``total``.

    Returns:
        int: The tokens outside the subset, never negative.
    """
    return max(0, (non_negative_int(total) or 0) - (non_negative_int(detail) or 0))


def _extract_usage(message: object) -> TokenUsage | None:
    """Read the token usage OpenRouter reports on a chat completion.

    OpenRouter answers with the OpenAI-compatible usage payload, surfaced by
    ``langchain-openai`` as ``response_metadata['token_usage']``; the
    standardized ``usage_metadata`` is only a fallback because it drops the
    reasoning and cached token details. Cached and reasoning tokens are subsets
    of the prompt/completion totals, so they are split out with
    :func:`_exclusive` to keep the counters disjoint.

    Args:
        message: The response message returned by the chat model.

    Returns:
        TokenUsage | None: The reported usage, or None when the response carried
            no counters.
    """
    metadata = getattr(message, "response_metadata", None) or {}
    token_usage = metadata.get("token_usage") if isinstance(metadata, dict) else None
    if isinstance(token_usage, dict) and token_usage:
        prompt_details = token_usage.get("prompt_tokens_details") or {}
        completion_details = token_usage.get("completion_tokens_details") or {}
        cache_read = non_negative_int(prompt_details.get("cached_tokens")) or 0
        reasoning = non_negative_int(completion_details.get("reasoning_tokens")) or 0
        return TokenUsage(
            input=_exclusive(token_usage.get("prompt_tokens"), cache_read),
            output=_exclusive(token_usage.get("completion_tokens"), reasoning),
            reasoning=reasoning,
            cache_read=cache_read,
        )

    usage_metadata = getattr(message, "usage_metadata", None)
    if isinstance(usage_metadata, dict) and usage_metadata:
        input_details = usage_metadata.get("input_token_details") or {}
        output_details = usage_metadata.get("output_token_details") or {}
        cache_read = non_negative_int(input_details.get("cache_read")) or 0
        reasoning = non_negative_int(output_details.get("reasoning")) or 0
        return TokenUsage(
            input=_exclusive(usage_metadata.get("input_tokens"), cache_read),
            output=_exclusive(usage_metadata.get("output_tokens"), reasoning),
            reasoning=reasoning,
            cache_read=cache_read,
        )
    return None


async def _record_llm_call(
    *,
    task_id: str | None,
    step: str,
    environment: SessionEnvironment | None = None,
    message: object | None = None,
    error: str | None = None,
) -> None:
    """Record a direct LLM call in the session history, best effort.

    The call is only recorded when it belongs to a task. A persistence failure
    never fails the workflow step whose call already succeeded, so it is logged
    and swallowed.

    Args:
        task_id: The Linear task identifier, or None outside a session.
        step: The prompt name recorded as the history step.
        environment: Optional resolved env layer supplying the model name.
        message: The response message carrying the reported usage, or None.
        error: The failure reason recorded for a failed call.
    """
    if task_id is None:
        return

    try:
        await record_llm_call(
            task_id=task_id,
            step=step,
            model=resolve_llm_model(environment),
            usage=_extract_usage(message) if message is not None else None,
            message=error,
        )
    except (EnvironmentConfigError, OSError, RuntimeError, SQLAlchemyError):
        logger.exception("Failed to record the LLM call for %s (%s)", task_id, step)


async def extract_questions(
    plan_output: str, *, task_id: str | None = None, environment: SessionEnvironment | None = None
) -> list[str]:
    """Extract open questions from a plan output when explicitly signalled.

    The plan agent emits an explicit terminal marker; extraction only runs
    when that marker is present, otherwise the LLM tends to fabricate
    questions out of the plan's build steps and verification notes.

    Args:
        plan_output: The raw plan agent output.
        task_id: Optional task id used to record the call in the session history.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        list[str]: The extracted questions, or an empty list when none were
            signalled.
    """
    from demetra.services.agents.opencode import PLAN_HAS_QUESTIONS

    if PLAN_HAS_QUESTIONS not in plan_output:
        return []

    result = []
    message = None
    try:
        llm = await build_llm(temperature=0.1, max_tokens=1024, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="extract_questions")),
                ("human", "Text: {input_text}"),
            ]
        )
        output_parser = NumberedListOutputParser()

        chain = prompt | llm
        message = await chain.ainvoke(input={"input_text": plan_output})
        parsed = output_parser.parse(text=str(message.content))

        for item in parsed:
            if question := str(item):
                result.append(question)
    except Exception as e:
        logger.exception("LLM call failed in extract_questions")
        await _record_llm_call(
            task_id=task_id,
            step="extract_questions",
            environment=environment,
            message=message,
            error=str(e),
        )
        raise PlanError("Failed to extract plan questions") from None

    await _record_llm_call(task_id=task_id, step="extract_questions", environment=environment, message=message)
    return result


async def summarize_review(
    review_output: str, *, task_id: str | None = None, environment: SessionEnvironment | None = None
) -> list[str]:
    """Summarize the critical findings from a noisy review agent output.

    The review agent output is noisy (thinking prose, no-issue affirmations)
    and the LLM is good at telling actual CRITICAL/ERROR findings apart from
    the rest. The LLM call is skipped entirely when there is no input.

    Args:
        review_output: The raw review agent output.
        task_id: Optional task id used to record the call in the session history.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        list[str]: De-duplicated review findings, or an empty list.
    """
    if not review_output or not review_output.strip():
        return []

    seen: set[str] = set()
    result: list[str] = []
    message = None
    try:
        llm = await build_llm(temperature=0.1, max_tokens=1024, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="summarize_review")),
                ("human", "Text: {input_text}"),
            ]
        )
        output_parser = NumberedListOutputParser()

        chain = prompt | llm
        message = await chain.ainvoke(input={"input_text": review_output})
        parsed = output_parser.parse(text=str(message.content))

        for item in parsed:
            if finding := str(item).strip():
                key = finding.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(finding)
    except Exception as e:
        logger.exception("LLM call failed in summarize_review")
        await _record_llm_call(
            task_id=task_id,
            step="summarize_review",
            environment=environment,
            message=message,
            error=str(e),
        )
        raise ReviewError("Failed to summarize the review") from None

    await _record_llm_call(task_id=task_id, step="summarize_review", environment=environment, message=message)
    return result


async def process_text_with_openrouter(
    text: str, *, task_id: str | None = None, environment: SessionEnvironment | None = None
) -> dict[str, str]:
    """Analyze a task text and return a structured ticket breakdown.

    Uses an LLM to split the text into title, description, technical
    requirements, acceptance criteria and project name. Falls back to a
    naive breakdown when the LLM returns nothing or the output does not
    carry all five ticket fields as strings.

    Args:
        text: The raw task text to analyze.
        task_id: Optional task id used to record the call in the session history.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        dict[str, str]: The structured ticket fields.
    """
    message = None
    try:
        llm = await build_llm(temperature=0.3, max_tokens=2048, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="analyze_ticket")),
                ("human", "Text: {input_text}"),
            ]
        )
        output_parser = JsonOutputParser()

        chain = prompt | llm
        message = await chain.ainvoke(input={"input_text": text})
        result = output_parser.parse(text=str(message.content))
    except Exception as e:
        logger.exception("LLM call failed in process_text_with_openrouter")
        await _record_llm_call(
            task_id=task_id,
            step="analyze_ticket",
            environment=environment,
            message=message,
            error=str(e),
        )
        result = None
    else:
        await _record_llm_call(task_id=task_id, step="analyze_ticket", environment=environment, message=message)
    if isinstance(result, dict) and all(isinstance(result.get(field), str) for field in TICKET_FIELDS):
        return {field: result[field] for field in TICKET_FIELDS}

    return {
        "title": text[:100] if len(text) > 100 else text,
        "description": text,
        "technical_requirements": "",
        "acceptance_criteria": "",
        "project_name": "",
    }


async def extract_plan(
    plan_output: str,
    task_description: str,
    comments: list[str],
    *,
    task_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> str:
    """Condense a raw plan output into a concise build plan summary.

    Truncates the plan output to the last PLAN_OUTPUT_MAX_CHARS and asks the
    LLM to summarize it in the context of the task description and comments.
    The truncation caps plan outputs that can reach hundreds of thousands of
    tokens against the 128k+ token contexts of the gpt-oss and deepseek
    models served through OpenRouter.

    Args:
        plan_output: The raw plan agent output.
        task_description: The original task description.
        comments: Any additional comments on the task.
        task_id: Optional task id used to record the call in the session history.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        str: The summarized build plan.
    """
    plan_output = plan_output[-PLAN_OUTPUT_MAX_CHARS:]

    task_description_full = (
        f"{task_description}\n\nComments:\n{chr(10).join(comments)}" if comments else task_description
    )

    try:
        llm = await build_llm(temperature=0.1, max_tokens=2048, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="summarize_plan")),
                ("human", "Task Description:\n{task_description}\n\nPlan Output:\n{plan_output}"),
            ]
        )

        chain = prompt | llm
        result = await chain.ainvoke(input={"task_description": task_description_full, "plan_output": plan_output})
    except Exception as e:
        logger.exception("LLM call failed in extract_plan")
        await _record_llm_call(task_id=task_id, step="summarize_plan", environment=environment, error=str(e))
        raise PlanError("Failed to summarize the build plan") from None

    await _record_llm_call(task_id=task_id, step="summarize_plan", environment=environment, message=result)
    return str(result.content)


async def compose_wiki_page(
    *,
    title: str,
    page_type: str,
    ticket_text: str,
    description: str,
    build_plan: str,
    diff_summary: str,
    diff_excerpt: str,
    log_tail: str,
    linear_url: str,
    related: list[str],
    task_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> str:
    """Author the Markdown body of a wiki page from the session facts.

    The wiki write side owns the frontmatter, the filename and the index entry;
    this call produces everything from the first ``##`` heading down. There is
    no deterministic scaffold to fall back on, so a failed call raises
    ``WikiError`` and the session commits without a page.

    Args:
        title: The page title, rendered as the H1 above the returned body.
        page_type: The page type driving the section presets.
        ticket_text: The Linear ticket body formatted for LLM consumption.
        description: The Linear ticket description.
        build_plan: The session build plan, or an empty string.
        diff_summary: The git diff stat text, or an empty string.
        diff_excerpt: A bounded excerpt of the unified diff holding the changed
            lines, or an empty string. This is the only source of real code and
            ``file:line`` evidence in the prompt.
        log_tail: The tail of the session log, or an empty string.
        linear_url: The Linear ticket URL for the References section.
        related: Filenames of sibling wiki pages to cross-link in the References
            section. Required by the output contract, so it must be supplied
            even when empty.
        task_id: Optional task id used to record the call in the session history.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        str: The page body Markdown, starting at the first ``##`` heading.

    Raises:
        WikiError: When the LLM call fails, returns no usable body, or returns a
            body that does not carry every ``WIKI_REQUIRED_SECTIONS`` heading.
    """
    related_links = "\n".join(f"- Related: [[{Path(name).stem}]]" for name in related) or "- None"
    template_input = {
        "title": title,
        "page_type": page_type,
        "ticket_text": ticket_text,
        "description": description,
        "build_plan": build_plan,
        "diff_summary": diff_summary,
        "diff_excerpt": diff_excerpt,
        "log_tail": log_tail,
        "linear_url": linear_url,
        "related": related_links,
    }
    try:
        llm = await build_llm(temperature=0.3, max_tokens=4096, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="compose_wiki_page")),
                (
                    "human",
                    "Page type: {page_type}\n\nTitle: {title}\n\nTicket:\n{ticket_text}\n\n"
                    "Description:\n{description}\n\nBuild plan:\n{build_plan}\n\n"
                    "Diff summary:\n{diff_summary}\n\nDiff excerpt:\n{diff_excerpt}\n\n"
                    "Session log tail:\n{log_tail}\n\n"
                    "Linear ticket URL: {linear_url}\n\nSibling pages to cross-link:\n{related}",
                ),
            ]
        )

        chain = prompt | llm
        result = await chain.ainvoke(input=template_input)
    except Exception as e:
        logger.exception("LLM call failed in compose_wiki_page")
        await _record_llm_call(task_id=task_id, step="compose_wiki_page", environment=environment, error=str(e))
        raise WikiError("Failed to compose the wiki page body") from None

    await _record_llm_call(task_id=task_id, step="compose_wiki_page", environment=environment, message=result)

    body = str(result.content).strip()
    if not body:
        logger.error("compose_wiki_page returned an empty body")
        raise WikiError("LLM returned an empty wiki page body")
    missing = [section for section in WIKI_REQUIRED_SECTIONS if section not in body]
    if missing:
        logger.error("compose_wiki_page body is missing required sections: %s", ", ".join(missing))
        raise WikiError(f"LLM returned a wiki page body missing required sections: {', '.join(missing)}")
    return body


async def generate_pr_description(
    task_details: str,
    build_plan: str | None = None,
    *,
    task_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> str:
    """Generate a pull request description from task details and build plan.

    Args:
        task_details: The task details to base the description on.
        build_plan: Optional build plan to include; a placeholder is used when
            absent.
        task_id: Optional task id used to record the call in the session history.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        str: The generated PR description.

    Raises:
        PrDescriptionError: When the LLM call fails.
    """
    try:
        llm = await build_llm(temperature=0.1, max_tokens=1024, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="generate_pr_description")),
                ("human", "Task details:\n{task_details}\n\nImplementation plan:\n{build_plan}"),
            ]
        )

        chain = prompt | llm
        result = await chain.ainvoke(
            input={
                "task_details": task_details,
                "build_plan": build_plan or "No build plan available.",
            }
        )
    except Exception as e:
        logger.exception("LLM call failed in generate_pr_description")
        await _record_llm_call(task_id=task_id, step="generate_pr_description", environment=environment, error=str(e))
        raise PrDescriptionError("Failed to generate the PR description") from None

    await _record_llm_call(task_id=task_id, step="generate_pr_description", environment=environment, message=result)
    return str(result.content).strip()
