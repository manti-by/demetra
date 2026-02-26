import re

from langchain_core.output_parsers import BaseOutputParser


class NumberedListOutputParser(BaseOutputParser[list[str]]):
    """Parse a numbered list (1. item / 1) item) into a Python list."""

    def parse(self, text: str) -> list[str]:
        lines = text.strip().splitlines()
        results: list[str] = []
        for line in lines:
            cleaned = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
            if cleaned:
                results.append(cleaned)
        return results

    @property
    def _type(self) -> str:
        return "numbered_list"
