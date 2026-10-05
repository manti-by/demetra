"""Settings-layer fallback for workflow environment keys.

:class:`~demetra.library.models.SessionEnvironment` resolves a key through the
project env, then the user-shared env, and finally the ``settings.py`` defaults
exposed here. The settings module is read at call time so tests can patch
``demetra.settings`` attributes without re-importing anything.
"""

from demetra import settings


def settings_default(key: str) -> str | None:
    """Return the ``settings.py`` default for a workflow environment key.

    Args:
        key: The environment variable name.

    Returns:
        str | None: The configured default, or None when settings does not
            define the key.
    """
    if key == "OPENROUTER_API_KEY":
        return settings.OPENROUTER["api_key"]
    if key == "OPENROUTER_MODEL":
        return settings.OPENROUTER["model"]
    if key == "OPENROUTER_BASE_URL":
        return settings.OPENROUTER["base_url"]
    if key == "LANGSMITH_TRACING":
        return "true" if settings.LANGSMITH["tracing"] else "false"
    if key == "LANGSMITH_ENDPOINT":
        return settings.LANGSMITH["endpoint"]
    if key == "LANGSMITH_API_KEY":
        return settings.LANGSMITH["api_key"]
    if key == "LANGSMITH_PROJECT":
        return settings.LANGSMITH["project"]
    if key == "LINEAR_TEAM_ID":
        return settings.LINEAR["team_id"]
    if key == "LINEAR_DEFAULT_STATE_ID":
        return settings.LINEAR["default_state"]
    if key == "ISSUE_TRACKER":
        return settings.ISSUE_TRACKER
    if key == "CLICKUP_TEAM_ID":
        return settings.CLICKUP["team_id"]
    if key == "CLICKUP_LIST_ID":
        return settings.CLICKUP["list_id"]
    if key == "CLICKUP_DEFAULT_STATE":
        return settings.CLICKUP["default_state"]
    if key.startswith("CLICKUP_STATE_"):
        state = key[len("CLICKUP_STATE_") :].lower()
        states = {name: value for name, value in dict(settings.CLICKUP["states"]).items() if isinstance(value, str)}
        return states.get(state)
    if key == "AGENT_HARNESS":
        return settings.AGENT_HARNESS
    if key == "OPENCODE_REVIEW_MODELS":
        return ",".join(settings.OPENCODE["review_models"])
    if key == "CLAUDE_REVIEW_MODELS":
        return ",".join(settings.CLAUDE["review_models"])
    if key == "CLAUDE_MAX_BUDGET_USD":
        return str(settings.CLAUDE_DEFAULT_MAX_BUDGET_USD)
    if key.startswith("OPENCODE_") and key.endswith("_MODEL"):
        agent = key[len("OPENCODE_") : -len("_MODEL")].lower()
        opencode_models = {
            "plan": settings.OPENCODE["plan_model"],
            "build": settings.OPENCODE["build_model"],
            "resolve": settings.OPENCODE["resolve_model"],
            "validate": settings.OPENCODE["validate_model"],
            "research": settings.OPENCODE["research_model"],
        }
        return opencode_models.get(agent)
    if key.startswith("CLAUDE_") and key.endswith("_MAX_BUDGET_USD"):
        agent = key[len("CLAUDE_") : -len("_MAX_BUDGET_USD")].lower()
        return str(settings.CLAUDE_MAX_BUDGET_USD.get(agent, settings.CLAUDE_DEFAULT_MAX_BUDGET_USD))
    if key.startswith("CLAUDE_") and key.endswith("_MODEL"):
        agent = key[len("CLAUDE_") : -len("_MODEL")].lower()
        claude_models = {
            "plan": settings.CLAUDE["plan_model"],
            "build": settings.CLAUDE["build_model"],
            "resolve": settings.CLAUDE["resolve_model"],
            "validate": settings.CLAUDE["validate_model"],
            "research": settings.CLAUDE["research_model"],
        }
        return claude_models.get(agent)
    if key.startswith("CLAUDE_") and key.endswith("_EFFORT"):
        agent = key[len("CLAUDE_") : -len("_EFFORT")].lower()
        claude_efforts = {
            "plan": settings.CLAUDE["plan_effort"],
            "build": settings.CLAUDE["build_effort"],
            "resolve": settings.CLAUDE["resolve_effort"],
            "validate": settings.CLAUDE["validate_effort"],
            "research": settings.CLAUDE["research_effort"],
        }
        return claude_efforts.get(agent)
    if key.startswith("LINEAR_STATE_") and key.endswith("_ID"):
        state = key[len("LINEAR_STATE_") : -len("_ID")].lower()
        states = {name: value for name, value in dict(settings.LINEAR["states"]).items() if isinstance(value, str)}
        return states.get(state)
    return None
