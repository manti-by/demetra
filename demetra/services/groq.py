import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from demetra.services.parser import NumberedListOutputParser
from demetra.services.prompt import get_prompt
from demetra.settings import GROQ_API_KEY


async def extract_questions(plan_output: str) -> list[str]:
    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.1, max_tokens=1024, max_retries=2)
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
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not configured")

    llm = ChatGroq(model="llama-3.1-8b-instant", temperature=0.2, max_tokens=2048, max_retries=2)

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a ticket analyzer. Analyze the given text and extract structured information for a Linear ticket.

Extract the following fields:
- title: A short, clear title for the ticket (max 100 chars)
- description: A detailed description of what needs to be done
- tech_requirements: Technical requirements or implementation details
- acceptance_criteria: What needs to be completed to consider this done

Return a JSON object with these fields. If any field is not applicable, use an empty string.
Do not include any markdown formatting in the output - just plain text.""",
            ),
            ("human", "Text: {input_text}"),
        ]
    )

    chain = prompt | llm
    result = await chain.ainvoke({"input_text": text})

    try:
        content = str(result.content)
    except (TypeError, ValueError):
        content = ""

    if not content:
        return {
            "title": text[:100] if len(text) > 100 else text,
            "description": text,
            "tech_requirements": "",
            "acceptance_criteria": "",
        }

    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    try:
        parsed = json.loads(content.strip())
        return {
            "title": parsed.get("title", ""),
            "description": parsed.get("description", ""),
            "tech_requirements": parsed.get("tech_requirements", ""),
            "acceptance_criteria": parsed.get("acceptance_criteria", ""),
        }
    except json.JSONDecodeError:
        return {
            "title": text[:100] if len(text) > 100 else text,
            "description": text,
            "tech_requirements": "",
            "acceptance_criteria": "",
        }
