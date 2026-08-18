import logging

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from demetra.library.exceptions import PlanError
from demetra.services.agents.opencode import PLAN_HAS_QUESTIONS
from demetra.services.llm.factory import build_llm
from demetra.services.llm.parser import NumberedListOutputParser
from demetra.services.llm.prompt import get_prompt


logger = logging.getLogger(__name__)


PLAN_OUTPUT_MAX_CHARS = 32_000

TICKET_FIELDS = ("title", "description", "technical_requirements", "acceptance_criteria", "project_name")


async def extract_questions(plan_output: str, *, user_environment: dict[str, str] | None = None) -> list[str]:
    """Extract open questions from a plan output when explicitly signalled.

    The plan agent emits an explicit terminal marker; extraction only runs
    when that marker is present, otherwise the LLM tends to fabricate
    questions out of the plan's build steps and verification notes.

    Args:
        plan_output: The raw plan agent output.
        user_environment: Optional user env layer for the LLM configuration.

    Returns:
        list[str]: The extracted questions, or an empty list when none were
            signalled.
    """
    if PLAN_HAS_QUESTIONS not in plan_output:
        return []

    llm = build_llm(temperature=0.1, max_tokens=1024, user_environment=user_environment)
    prompt = ChatPromptTemplate.from_messages(
        messages=[
            ("system", await get_prompt(name="extract_questions")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = NumberedListOutputParser()

    chain = prompt | llm | output_parser

    result = []
    for item in await chain.ainvoke(input={"input_text": plan_output}):
        if question := str(item):
            result.append(question)
    return result


async def summarize_review(review_output: str, *, user_environment: dict[str, str] | None = None) -> list[str]:
    """Summarize the critical findings from a noisy review agent output.

    The review agent output is noisy (thinking prose, no-issue affirmations)
    and the LLM is good at telling actual CRITICAL/ERROR findings apart from
    the rest. The LLM call is skipped entirely when there is no input.

    Args:
        review_output: The raw review agent output.
        user_environment: Optional user env layer for the LLM configuration.

    Returns:
        list[str]: De-duplicated review findings, or an empty list.
    """
    if not review_output or not review_output.strip():
        return []

    llm = build_llm(temperature=0.1, max_tokens=1024, user_environment=user_environment)
    prompt = ChatPromptTemplate.from_messages(
        messages=[
            ("system", await get_prompt(name="summarize_review")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = NumberedListOutputParser()

    chain = prompt | llm | output_parser

    seen: set[str] = set()
    result: list[str] = []
    try:
        for item in await chain.ainvoke(input={"input_text": review_output}):
            if finding := str(item).strip():
                key = finding.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(finding)
    except Exception:
        logger.exception("LLM call failed in summarize_review")
        return []
    return result


async def process_text_with_openrouter(text: str, *, user_environment: dict[str, str] | None = None) -> dict[str, str]:
    """Analyze a task text and return a structured ticket breakdown.

    Uses an LLM to split the text into title, description, technical
    requirements, acceptance criteria and project name. Falls back to a
    naive breakdown when the LLM returns nothing or the output does not
    carry all five ticket fields as strings.

    Args:
        text: The raw task text to analyze.
        user_environment: Optional user env layer for the LLM configuration.

    Returns:
        dict[str, str]: The structured ticket fields.
    """
    llm = build_llm(temperature=0.3, max_tokens=2048, user_environment=user_environment)
    prompt = ChatPromptTemplate.from_messages(
        messages=[
            ("system", await get_prompt(name="analyze_ticket")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = JsonOutputParser()

    chain = prompt | llm | output_parser
    try:
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
    plan_output: str, task_description: str, comments: list[str], *, user_environment: dict[str, str] | None = None
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
        user_environment: Optional user env layer for the LLM configuration.

    Returns:
        str: The summarized build plan.
    """
    plan_output = plan_output[-PLAN_OUTPUT_MAX_CHARS:]

    task_description_full = (
        f"{task_description}\n\nComments:\n{chr(10).join(comments)}" if comments else task_description
    )

    llm = build_llm(temperature=0.1, max_tokens=2048, user_environment=user_environment)
    prompt = ChatPromptTemplate.from_messages(
        messages=[
            ("system", await get_prompt(name="summarize_plan")),
            ("human", "Task Description:\n{task_description}\n\nPlan Output:\n{plan_output}"),
        ]
    )

    chain = prompt | llm
    try:
        result = await chain.ainvoke(input={"task_description": task_description_full, "plan_output": plan_output})
    except Exception:
        logger.exception("LLM call failed in extract_plan")
        raise PlanError("Failed to summarize the build plan") from None
    return str(result.content)


async def summarize_session(
    ticket_text: str,
    description: str,
    build_plan: str,
    diff_summary: str,
    *,
    user_environment: dict[str, str] | None = None,
) -> dict[str, str]:
    """Generate a wiki page TL;DR and overview for an implementation session.

    The wiki write side uses this as its optional second pass: when the
    deterministic scaffold exceeds the LLM budget, the LLM polishes the
    TL;DR and overview sections from the ticket, plan and diff facts.

    Args:
        ticket_text: The Linear ticket body formatted for LLM consumption.
        description: The Linear ticket description.
        build_plan: The session build plan, or an empty string.
        diff_summary: The git diff stat text, or an empty string.
        user_environment: Optional user env layer for the LLM configuration.

    Returns:
        dict[str, str]: A mapping with ``tldr`` and ``overview`` keys, or an
            empty dict when the LLM call fails.
    """
    llm = build_llm(temperature=0.1, max_tokens=1024, user_environment=user_environment)
    prompt = ChatPromptTemplate.from_messages(
        messages=[
            ("system", await get_prompt(name="summarize_session")),
            (
                "human",
                "Ticket:\n{ticket_text}\n\nDescription:\n{description}\n\n"
                "Build plan:\n{build_plan}\n\nDiff summary:\n{diff_summary}",
            ),
        ]
    )
    output_parser = JsonOutputParser()

    chain = prompt | llm | output_parser
    try:
        result = await chain.ainvoke(
            input={
                "ticket_text": ticket_text,
                "description": description,
                "build_plan": build_plan,
                "diff_summary": diff_summary,
            }
        )
        if not isinstance(result, dict):
            logger.warning("summarize_session returned non-dict output: %r", type(result).__name__)
            return {}
        return {
            "tldr": str(result.get("tldr") or "").strip(),
            "overview": str(result.get("overview") or "").strip(),
        }
    except Exception:
        logger.exception("LLM call failed in summarize_session")
        return {}


async def generate_pr_description(
    task_details: str, build_plan: str | None = None, *, user_environment: dict[str, str] | None = None
) -> str:
    """Generate a pull request description from task details and build plan.

    Args:
        task_details: The task details to base the description on.
        build_plan: Optional build plan to include; a placeholder is used when
            absent.
        user_environment: Optional user env layer for the LLM configuration.

    Returns:
        str: The generated PR description, or an empty string on failure.
    """
    llm = build_llm(temperature=0.1, max_tokens=1024, user_environment=user_environment)
    prompt = ChatPromptTemplate.from_messages(
        messages=[
            ("system", await get_prompt(name="generate_pr_description")),
            ("human", "Task details:\n{task_details}\n\nImplementation plan:\n{build_plan}"),
        ]
    )

    chain = prompt | llm
    try:
        result = await chain.ainvoke(
            input={
                "task_details": task_details,
                "build_plan": build_plan or "No build plan available.",
            }
        )
        return str(result.content).strip()
    except Exception:
        logger.exception("LLM call failed in generate_pr_description")
        return ""
