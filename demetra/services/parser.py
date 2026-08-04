import re

from langchain_core.output_parsers import BaseOutputParser


class NumberedListOutputParser(BaseOutputParser[list[str]]):
    """Parse a numbered list (1. item / 1) item) into a Python list."""

    def parse(self, text: str) -> list[str]:
        """Parse a numbered list into a plain list of items.

        Strips leading ``1.`` or ``1)`` numbering from each line and drops
        empty entries.

        Args:
            text: The numbered list text to parse.

        Returns:
            list[str]: The parsed items.
        """
        lines = text.strip().splitlines()
        results: list[str] = []
        for line in lines:
            cleaned = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
            if cleaned:
                results.append(cleaned)
        return results

    @property
    def _type(self) -> str:
        """Return the parser type identifier used by LangChain.

        Returns:
            str: The type name ``"numbered_list"``.
        """
        return "numbered_list"
