from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from demetra.services.opencode import PLAN_HAS_QUESTIONS
from demetra.services.parser import NumberedListOutputParser
from demetra.services.prompt import get_prompt
from demetra.settings import GROQ


async def extract_questions(plan_output: str) -> list[str]:
    # The plan agent emits an explicit terminal marker. Only run extraction when it
    # signalled open questions; otherwise the LLM tends to fabricate questions out of
    # the plan's build steps and verification notes.
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
    # The review agent output is noisy (thinking prose, no-issue affirmations) and
    # the LLM is good at telling actual CRITICAL/ERROR findings apart from the
    # rest. Skip the LLM call entirely when there is nothing to feed it.
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

    result = []
    for item in await chain.ainvoke({"input_text": review_output}):
        if finding := str(item).strip():
            result.append(finding)
    return result


async def process_text_with_groq(text: str) -> dict[str, str]:
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
        "tech_requirements": "",
        "acceptance_criteria": "",
        "project_name": "",
    }


async def extract_plan(plan_output: str, task_description: str, comments: list[str]) -> str:
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
