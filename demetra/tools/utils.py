from demetra.settings import SEARCH


def resolve_limit(arguments: dict) -> int:
    """Clamp the ``limit`` tool argument into the configured result range.

    Args:
        arguments: The raw tool arguments mapping.

    Returns:
        int: A usable limit, falling back to the default for missing or
            non-numeric values.
    """
    try:
        limit = int(arguments.get("limit", SEARCH["default_limit"]))
    except (TypeError, ValueError):
        return SEARCH["default_limit"]
    return min(max(limit, 1), SEARCH["max_results"])
