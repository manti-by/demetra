import aiofiles

from demetra.settings import BASE_PATH


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
