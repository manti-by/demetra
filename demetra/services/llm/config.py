import demetra.services.llm as service
from demetra.library.types import OpenRouterConfig


async def get_openrouter_config(*, user_id: str | None = None) -> OpenRouterConfig:
    """Resolve the OpenRouter config from the user-shared env or the settings.

    ``OPENROUTER_API_KEY`` and ``OPENROUTER_MODEL`` resolve to the matching
    keys in the user's shared environment, falling back to the settings
    defaults when the user has no override. ``OPENROUTER_BASE_URL`` always
    comes from settings.

    Args:
        user_id: Optional user id whose shared environment is consulted.

    Returns:
        OpenRouterConfig: The resolved OpenRouter config with the user overrides
            applied.
    """
    user_environment: dict[str, str] = {}
    if user_id:
        user_environment = await service.get_user_environments_decrypted(user_id=user_id)

    api_key = user_environment.get("OPENROUTER_API_KEY") or service.OPENROUTER["api_key"]
    model = user_environment.get("OPENROUTER_MODEL") or service.OPENROUTER["model"]
    return {
        "api_key": api_key,
        "model": model,
        "base_url": service.OPENROUTER["base_url"],
    }
