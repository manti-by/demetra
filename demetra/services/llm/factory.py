from langchain_openai import ChatOpenAI

from demetra.settings import OPENROUTER


def build_llm(*, temperature: float, max_tokens: int, max_retries: int = 2) -> ChatOpenAI:
    """Build a chat model backed by OpenRouter.

    Centralizes the model instantiation so changing the model or endpoint
    is a one-line config change instead of touching every chain.

    Args:
        temperature: Sampling temperature for the model.
        max_tokens: Maximum number of tokens to generate.
        max_retries: Number of retries on transient API failures.

    Returns:
        ChatOpenAI: The configured chat model.
    """
    return ChatOpenAI(
        model=OPENROUTER["model"],
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        api_key=OPENROUTER["api_key"],
        base_url=OPENROUTER["base_url"],
    )
