from langchain_openai import ChatOpenAI

from demetra.settings import OPENROUTER


def build_llm(
    *,
    temperature: float,
    max_tokens: int,
    max_retries: int = 2,
    user_environment: dict[str, str] | None = None,
) -> ChatOpenAI:
    """Build a chat model backed by OpenRouter.

    Centralizes the model instantiation so changing the model or endpoint
    is a one-line config change instead of touching every chain. The user
    environment can override the model and API key.

    Args:
        temperature: Sampling temperature for the model.
        max_tokens: Maximum number of tokens to generate.
        max_retries: Number of retries on transient API failures.
        user_environment: Optional user env layer overriding the model and
            API key via ``OPENROUTER_MODEL`` and ``OPENROUTER_API_KEY``.

    Returns:
        ChatOpenAI: The configured chat model.
    """
    user_env = user_environment or {}
    return ChatOpenAI(
        model=user_env.get("OPENROUTER_MODEL", OPENROUTER["model"]),
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        api_key=user_env.get("OPENROUTER_API_KEY", OPENROUTER["api_key"]),
        base_url=OPENROUTER["base_url"],
    )
