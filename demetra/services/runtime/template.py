import aiofiles

from demetra.library.models import ChatTemplate
from demetra.settings import BASE_PATH


CHAT_TEMPLATES_DIR = BASE_PATH / "demetra" / "templates" / "chat"


async def get_template(name: str, **kwargs) -> str:
    """Load and render a message template by name.

    Templates live in ``demetra/templates/`` and are rendered with Python
    ``str.format``, matching the prompt delivery path: single
    ``{placeholder}`` for substitution; any literal brace must be escaped as
    ``{{`` / ``}}``. Without kwargs the raw template text is returned.

    Args:
        name: The template file name without the ``.md`` extension.
        kwargs: Substitution values for the template placeholders.

    Returns:
        str: The rendered template text.
    """
    async with aiofiles.open(BASE_PATH / f"demetra/templates/{name}.md") as file:
        content = await file.read()
    if kwargs:
        return content.format(**kwargs)
    return content


async def list_chat_templates() -> list[ChatTemplate]:
    """Load the chat templates shipped in ``demetra/templates/chat/``.

    Every ``*.md`` file in the directory becomes a template, sorted by file
    stem. The file stem is the ``name``, and the stem with underscores turned
    into spaces is the human-readable ``label`` (``feature_template.md``
    becomes ``Feature Template``). Unreadable files are skipped so one bad
    template cannot break the whole list.

    Returns:
        list[ChatTemplate]: The available chat templates.
    """
    templates: list[ChatTemplate] = []
    for path in sorted(CHAT_TEMPLATES_DIR.glob("*.md")):
        try:
            async with aiofiles.open(path) as file:
                content = await file.read()
        except OSError:
            continue
        templates.append(ChatTemplate(name=path.stem, label=path.stem.replace("_", " ").title(), content=content))
    return templates
