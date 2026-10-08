import logging
from pathlib import Path

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from demetra.library.constants import WIKI_REQUIRED_SECTIONS
from demetra.library.exceptions import PlanError, PrDescriptionError, ReviewError, WikiError
from demetra.library.models import SessionEnvironment
from demetra.services.llm.factory import build_llm
from demetra.services.llm.parser import NumberedListOutputParser
from demetra.services.llm.prompt import get_prompt


logger = logging.getLogger(__name__)


PLAN_OUTPUT_MAX_CHARS = 32_000

TICKET_FIELDS = ("title", "description", "technical_requirements", "acceptance_criteria", "project_name")


async def extract_questions(plan_output: str, *, environment: SessionEnvironment | None = None) -> list[str]:
    """Extract open questions from a plan output when explicitly signalled.

    The plan agent emits an explicit terminal marker; extraction only runs
    when that marker is present, otherwise the LLM tends to fabricate
    questions out of the plan's build steps and verification notes.

    Args:
        plan_output: The raw plan agent output.
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
    try:
        llm = await build_llm(temperature=0.1, max_tokens=1024, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="extract_questions")),
                ("human", "Text: {input_text}"),
            ]
        )
        output_parser = NumberedListOutputParser()

        chain = prompt | llm | output_parser

        for item in await chain.ainvoke(input={"input_text": plan_output}):
            if question := str(item):
                result.append(question)
    except Exception:
        logger.exception("LLM call failed in extract_questions")
        raise PlanError("Failed to extract plan questions") from None
    return result


async def summarize_review(review_output: str, *, environment: SessionEnvironment | None = None) -> list[str]:
    """Summarize the critical findings from a noisy review agent output.

    The review agent output is noisy (thinking prose, no-issue affirmations)
    and the LLM is good at telling actual CRITICAL/ERROR findings apart from
    the rest. The LLM call is skipped entirely when there is no input.

    Args:
        review_output: The raw review agent output.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        list[str]: De-duplicated review findings, or an empty list.
    """
    if not review_output or not review_output.strip():
        return []

    seen: set[str] = set()
    result: list[str] = []
    try:
        llm = await build_llm(temperature=0.1, max_tokens=1024, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="summarize_review")),
                ("human", "Text: {input_text}"),
            ]
        )
        output_parser = NumberedListOutputParser()

        chain = prompt | llm | output_parser

        for item in await chain.ainvoke(input={"input_text": review_output}):
            if finding := str(item).strip():
                key = finding.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(finding)
    except Exception:
        logger.exception("LLM call failed in summarize_review")
        raise ReviewError("Failed to summarize the review") from None
    return result


async def process_text_with_openrouter(text: str, *, environment: SessionEnvironment | None = None) -> dict[str, str]:
    """Analyze a task text and return a structured ticket breakdown.

    Uses an LLM to split the text into title, description, technical
    requirements, acceptance criteria and project name. Falls back to a
    naive breakdown when the LLM returns nothing or the output does not
    carry all five ticket fields as strings.

    Args:
        text: The raw task text to analyze.
        environment: Optional resolved env layer configuring the LLM via
            ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        dict[str, str]: The structured ticket fields.
    """
    try:
        llm = await build_llm(temperature=0.3, max_tokens=2048, environment=environment)
        prompt = ChatPromptTemplate.from_messages(
            messages=[
                ("system", await get_prompt(name="analyze_ticket")),
                ("human", "Text: {input_text}"),
            ]
        )
        output_parser = JsonOutputParser()

        chain = prompt | llm | output_parser
        result = await chain.ainvoke(input={"input_text": text})
    except Exception:
        logger.exception("LLM call failed in process_text_with_openrouter")
        result = None
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
    plan_output: str, task_description: str, comments: list[str], *, environment: SessionEnvironment | None = None
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
    except Exception:
        logger.exception("LLM call failed in extract_plan")
        raise PlanError("Failed to summarize the build plan") from None
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
    except Exception:
        logger.exception("LLM call failed in compose_wiki_page")
        raise WikiError("Failed to compose the wiki page body") from None

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
    task_details: str, build_plan: str | None = None, *, environment: SessionEnvironment | None = None
) -> str:
    """Generate a pull request description from task details and build plan.

    Args:
        task_details: The task details to base the description on.
        build_plan: Optional build plan to include; a placeholder is used when
            absent.
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
        return str(result.content).strip()
    except Exception:
        logger.exception("LLM call failed in generate_pr_description")
        raise PrDescriptionError("Failed to generate the PR description") from None
