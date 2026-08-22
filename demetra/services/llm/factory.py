from langchain_openai import ChatOpenAI

from demetra.services.llm.config import get_openrouter_config


async def build_llm(
    *,
    temperature: float,
    max_tokens: int,
    max_retries: int = 2,
    user_id: str | None = None,
) -> ChatOpenAI:
    """Build a chat model backed by OpenRouter.

    Centralizes the model instantiation so changing the model or endpoint
    is a one-line config change instead of touching every chain. The user
    environment can override the model and API key via ``OPENROUTER_MODEL``
    and ``OPENROUTER_API_KEY``.

    Args:
        temperature: Sampling temperature for the model.
        max_tokens: Maximum number of tokens to generate.
        max_retries: Number of retries on transient API failures.
        user_id: Optional user id whose shared environment configures the
            model and API key.

    Returns:
        ChatOpenAI: The configured chat model.
    """
    config = await get_openrouter_config(user_id=user_id)
    return ChatOpenAI(
        model=config["model"],
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        api_key=config["api_key"],
        base_url=config["base_url"],
    )
