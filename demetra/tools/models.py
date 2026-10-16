from collections.abc import Mapping
from dataclasses import dataclass

from mcp.types import TextContent


@dataclass
class ToolResult:
    """Outcome of an MCP tool call, shared by every tool module."""

    content: list[TextContent]
    is_error: bool = False


@dataclass(frozen=True)
class DocumentedFunction:
    """A function and its docstring extracted from the project source tree."""

    qualified_name: str
    path: str
    line: int
    docstring: str


@dataclass(frozen=True)
class Field:
    """Describe one searchable zone of a document and how BM25 scores it.

    Attributes:
        weight: Boost applied to the field's term frequency before saturation.
        length_norm: Strength of length normalization, from 0 (off) to 1 (full).
    """

    weight: float
    length_norm: float


@dataclass(frozen=True)
class FieldCounts:
    """Hold per-term token counts and the token length of one document field.

    Attributes:
        counts: Mapping of term to its occurrence count in the field.
        length: Total token count, retained so scoring never re-walks the text.
    """

    counts: Mapping[str, int]
    length: int


@dataclass(frozen=True)
class CorpusStats:
    """Hold corpus-wide BM25 statistics shared by every document.

    Attributes:
        document_count: Number of documents in the corpus.
        average_lengths: Mean token length per field, aligned with the field
            order the caller scores in.
        document_frequency: Mapping of term to the number of documents
            containing it.
    """

    document_count: int
    average_lengths: tuple[float, ...]
    document_frequency: Mapping[str, int]
