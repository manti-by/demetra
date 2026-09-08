import re

from demetra.settings import SEARCH


def tokenize(query: str) -> list[str]:
    """Split a query into lowercase terms, dropping stop words and short terms.

    Args:
        query: The raw search query.

    Returns:
        list[str]: The meaningful search terms.
    """
    return [
        term
        for term in re.findall(SEARCH["term_pattern"], query.lower())
        if term not in SEARCH["stop_words"] and len(term) >= SEARCH["min_term_length"]
    ]
