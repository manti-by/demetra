import aiofiles

from demetra.settings import BASE_PATH


async def get_prompt(name: str, **kwargs) -> str:
    """
    Load a prompt by name. There are two delivery paths with different brace rules:

    - With kwargs (e.g. merge_agent, rebase_agent, resolve_questions): rendered here
      via Python ``str.format``. Use single ``{placeholder}`` for substitution; any
      literal brace must be escaped as ``{{`` / ``}}``.
    - Without kwargs (e.g. analyze_ticket, summarize_plan, extract_questions,
      summarize_review, generate_pr_description): returned raw and handed to a
      LangChain ``ChatPromptTemplate`` (f-string mode), which fills placeholders from
      the chain inputs. Any literal brace there must also be doubled (``{{`` / ``}}``).
    """
    async with aiofiles.open(BASE_PATH / f"demetra/prompts/{name}.md") as file:
        content = await file.read()
    if kwargs:
        return content.format(**kwargs)
    return content
