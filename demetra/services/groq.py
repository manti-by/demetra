import logging

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from demetra.services.opencode import PLAN_HAS_QUESTIONS
from demetra.services.parser import NumberedListOutputParser
from demetra.services.prompt import get_prompt
from demetra.settings import GROQ


logger = logging.getLogger(__name__)


# llama-3.1-8b-instant has a 131k token context; plan outputs can reach hundreds of k tokens.
PLAN_OUTPUT_MAX_CHARS = 32_000


async def extract_questions(plan_output: str) -> list[str]:
    """Extract open questions from a plan output when explicitly signalled.

    The plan agent emits an explicit terminal marker; extraction only runs
    when that marker is present, otherwise the LLM tends to fabricate
    questions out of the plan's build steps and verification notes.

    Args:
        plan_output: The raw plan agent output.

    Returns:
        list[str]: The extracted questions, or an empty list when none were
            signalled.
    """
    if PLAN_HAS_QUESTIONS not in plan_output:
        return []

    llm = ChatGroq(model=GROQ["model"], temperature=0.1, max_tokens=1024, max_retries=2)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", await get_prompt(name="extract_questions")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = NumberedListOutputParser()

    chain = prompt | llm | output_parser

    result = []
    for item in await chain.ainvoke({"input_text": plan_output}):
        if question := str(item):
            result.append(question)
    return result


async def summarize_review(review_output: str) -> list[str]:
    """Summarize the critical findings from a noisy review agent output.

    The review agent output is noisy (thinking prose, no-issue affirmations)
    and the LLM is good at telling actual CRITICAL/ERROR findings apart from
    the rest. The LLM call is skipped entirely when there is no input.

    Args:
        review_output: The raw review agent output.

    Returns:
        list[str]: De-duplicated review findings, or an empty list.
    """
    if not review_output or not review_output.strip():
        return []

    llm = ChatGroq(model=GROQ["model"], temperature=0.1, max_tokens=1024, max_retries=2)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", await get_prompt(name="summarize_review")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = NumberedListOutputParser()

    chain = prompt | llm | output_parser

    seen: set[str] = set()
    result: list[str] = []
    try:
        for item in await chain.ainvoke({"input_text": review_output}):
            if finding := str(item).strip():
                key = finding.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(finding)
    except Exception:
        logger.exception("LLM call failed in summarize_review")
        return []
    return result


async def process_text_with_groq(text: str) -> dict[str, str]:
    """Analyze a task text and return a structured ticket breakdown.

    Uses an LLM to split the text into title, description, technical
    requirements, acceptance criteria and project name. Falls back to a
    naive breakdown when the LLM returns nothing.

    Args:
        text: The raw task text to analyze.

    Returns:
        dict[str, str]: The structured ticket fields.
    """
    llm = ChatGroq(model=GROQ["model"], temperature=0.3, max_tokens=2048, max_retries=2)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", await get_prompt(name="analyze_ticket")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = JsonOutputParser()

    chain = prompt | llm | output_parser
    if result := await chain.ainvoke({"input_text": text}):
        return result

    return {
        "title": text[:100] if len(text) > 100 else text,
        "description": text,
        "technical_requirements": "",
        "acceptance_criteria": "",
        "project_name": "",
    }


async def extract_plan(plan_output: str, task_description: str, comments: list[str]) -> str:
    """Condense a raw plan output into a concise build plan summary.

    Truncates the plan output to the last PLAN_OUTPUT_MAX_CHARS and asks the
    LLM to summarize it in the context of the task description and comments.

    Args:
        plan_output: The raw plan agent output.
        task_description: The original task description.
        comments: Any additional comments on the task.

    Returns:
        str: The summarized build plan.
    """
    plan_output = plan_output[-PLAN_OUTPUT_MAX_CHARS:]

    task_description_full = (
        f"{task_description}\n\nComments:\n{chr(10).join(comments)}" if comments else task_description
    )

    llm = ChatGroq(model=GROQ["model"], temperature=0.1, max_tokens=2048, max_retries=2)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", await get_prompt(name="summarize_plan")),
            ("human", "Task Description:\n{task_description}\n\nPlan Output:\n{plan_output}"),
        ]
    )

    chain = prompt | llm
    result = await chain.ainvoke({"task_description": task_description_full, "plan_output": plan_output})
    return str(result.content)


async def generate_pr_description(task_details: str, build_plan: str | None = None) -> str:
    """Generate a pull request description from task details and build plan.

    Args:
        task_details: The task details to base the description on.
        build_plan: Optional build plan to include; a placeholder is used when
            absent.

    Returns:
        str: The generated PR description, or an empty string on failure.
    """
    llm = ChatGroq(model=GROQ["model"], temperature=0.1, max_tokens=1024, max_retries=2)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", await get_prompt(name="generate_pr_description")),
            ("human", "Task details:\n{task_details}\n\nImplementation plan:\n{build_plan}"),
        ]
    )

    chain = prompt | llm
    try:
        result = await chain.ainvoke(
            {
                "task_details": task_details,
                "build_plan": build_plan or "No build plan available.",
            }
        )
        return str(result.content).strip()
    except Exception:
        logger.exception("LLM call failed in generate_pr_description")
        return ""
