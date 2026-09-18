from langchain_openai import ChatOpenAI

from demetra.library.models import SessionEnvironment


async def build_llm(
    *,
    temperature: float,
    max_tokens: int,
    max_retries: int = 2,
    environment: SessionEnvironment | None = None,
) -> ChatOpenAI:
    """Build a chat model backed by OpenRouter.

    Centralizes the model instantiation so changing the model or endpoint
    is a one-line config change instead of touching every chain. The resolved
    environment can override the model and API key via ``OPENROUTER_MODEL``
    and ``OPENROUTER_API_KEY``.

    Args:
        temperature: Sampling temperature for the model.
        max_tokens: Maximum number of tokens to generate.
        max_retries: Number of retries on transient API failures.
        environment: Optional resolved env layer configuring the model and
            API key; falls back to the settings-only layers when omitted.

    Returns:
        ChatOpenAI: The configured chat model.
    """
    resolver = environment or SessionEnvironment(project_environment={}, user_environment={})
    config = resolver.openrouter_config
    return ChatOpenAI(
        model=config["model"],
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        api_key=config["api_key"],
        base_url=config["base_url"],
    )
