import demetra.services.linear as service


async def get_linear_config_value(name: str, *, user_id: str | None = None) -> str | None:
    """Resolve a Linear config value from the user-shared env or the settings.

    State names resolve to the matching ``LINEAR_STATE_<NAME>_ID`` key in the
    user's shared environment, ``"default_state"`` to ``LINEAR_DEFAULT_STATE_ID``
    and any other name to ``LINEAR_<NAME>``. The settings default is used when
    the user has no override for the key.

    Args:
        name: The config name, e.g. ``"team_id"``, ``"default_state"`` or a
            state name like ``"todo"``.
        user_id: Optional user id whose shared environment is consulted.

    Returns:
        str | None: The resolved value, or None when no layer provides it.
    """
    if name in service.LINEAR["states"]:
        env_key = f"LINEAR_STATE_{name.upper()}_ID"
    elif name == "default_state":
        env_key = "LINEAR_DEFAULT_STATE_ID"
    else:
        env_key = f"LINEAR_{name.upper()}"

    if user_id:
        user_environment = await service.get_user_environments_decrypted(user_id=user_id)
        if env_key in user_environment:
            return user_environment[env_key]

    states = {key: value for key, value in dict(service.LINEAR["states"]).items() if isinstance(value, str)}
    if name in states:
        return states[name]
    value = dict(service.LINEAR).get(name)
    return value if isinstance(value, str) else None
