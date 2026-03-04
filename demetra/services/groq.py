from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from demetra.services.parser import NumberedListOutputParser
from demetra.services.prompt import get_prompt
from demetra.settings import GROQ


async def extract_questions(plan_output: str) -> list[str]:
    llm = ChatGroq(model=GROQ["model"], temperature=0.1, max_tokens=1024, max_retries=2)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", await get_prompt(name="extract_questions")),
            ("human", "Text: {input_text}"),
        ]
    )
    output_parser = NumberedListOutputParser()

    chain = prompt | llm | output_parser
    return await chain.ainvoke({"input_text": plan_output})


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
