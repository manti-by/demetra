import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from demetra.library.constants import SEARCH_STOP_WORDS
from demetra.settings import SEARCH


MIN_LENGTH_NORM_DIVISOR = 1e-6


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


def _terms(text: str) -> list[str]:
    """Split text into lowercase searchable terms.

    Args:
        text: The raw text to split.

    Returns:
        list[str]: Terms with stop words and very short tokens removed.
    """
    return [
        term
        for term in re.findall(SEARCH["term_pattern"], text.lower())
        if term not in SEARCH_STOP_WORDS and len(term) >= SEARCH["min_term_length"]
    ]


def tokenize(query: str) -> list[str]:
    """Split a query into lowercase terms, dropping stop words and short terms.

    The same analyzer runs over documents, so a term only ever matches a whole
    token rather than an arbitrary substring.

    Args:
        query: The raw search query.

    Returns:
        list[str]: The meaningful search terms.
    """
    return _terms(text=query)


def count_field(text: str) -> FieldCounts:
    """Count searchable tokens in a document field.

    Args:
        text: The raw field text.

    Returns:
        FieldCounts: Per-term counts paired with the field's token length.
    """
    counts = Counter(_terms(text=text))
    return FieldCounts(counts=counts, length=sum(counts.values()))


def build_stats(fields: Sequence[Field], documents: Sequence[Sequence[FieldCounts]]) -> CorpusStats:
    """Compute document frequencies and average field lengths for a corpus.

    A term contributes to its document frequency once per document no matter
    how many fields it appears in.

    Args:
        fields: The field descriptors, in the order documents align to.
        documents: Per-document field counts, aligned to ``fields``.

    Returns:
        CorpusStats: The statistics shared by every scoring call.
    """
    totals = [0] * len(fields)
    document_frequency: Counter = Counter()
    for document in documents:
        present: set[str] = set()
        for index, field_counts in enumerate(document):
            totals[index] += field_counts.length
            present.update(field_counts.counts)
        document_frequency.update(present)
    document_count = len(documents)
    return CorpusStats(
        document_count=document_count,
        average_lengths=tuple(total / document_count if document_count else 0.0 for total in totals),
        document_frequency=document_frequency,
    )


def inverse_document_frequency(document_frequency: int, document_count: int) -> float:
    """Return the smoothed BM25 inverse document frequency for one term.

    The ``log(1 + ...)`` form keeps the value positive for terms appearing in
    every document, which the uncorrected ratio would not.

    Args:
        document_frequency: Number of documents containing the term.
        document_count: Total number of documents in the corpus.

    Returns:
        float: The inverse document frequency weight.
    """
    return math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))


def score_document(
    fields: Sequence[Field],
    document: Sequence[FieldCounts],
    stats: CorpusStats,
    terms: Sequence[str],
) -> float:
    """Score one document against query terms using BM25F.

    Term frequencies from every field are length-normalized against their own
    field average and combined under that field's boost, then saturated once
    so that a term repeated many times cannot dominate the ranking.

    Args:
        fields: The field descriptors, in the order ``document`` aligns to.
        document: The document's per-field token counts.
        stats: Corpus statistics from ``build_stats``.
        terms: The normalized query terms.

    Returns:
        float: The relevance score, or 0.0 when no term matches.
    """
    if stats.document_count == 0:
        return 0.0
    k1 = SEARCH["bm25_k1"]
    divisors = []
    for index, field in enumerate(fields):
        average = stats.average_lengths[index]
        length = document[index].length
        ratio = length / average if average else 1.0
        divisors.append(max(1 - field.length_norm + field.length_norm * ratio, MIN_LENGTH_NORM_DIVISOR))
    score = 0.0
    for term in dict.fromkeys(terms):
        weighted = 0.0
        for index, field in enumerate(fields):
            occurrences = document[index].counts.get(term, 0)
            if occurrences:
                weighted += field.weight * occurrences / divisors[index]
        if weighted <= 0.0:
            continue
        idf = inverse_document_frequency(
            document_frequency=stats.document_frequency.get(term, 0),
            document_count=stats.document_count,
        )
        score += idf * (weighted * (k1 + 1)) / (weighted + k1)
    return score


def line_hits(line: str, terms: Sequence[str]) -> int:
    """Count how many query terms appear as whole tokens on one line.

    Args:
        line: The line text to scan.
        terms: The normalized query terms.

    Returns:
        int: The number of distinct matching terms, or 0 when none match.
    """
    tokens = set(_terms(text=line))
    return sum(1 for term in terms if term in tokens)
