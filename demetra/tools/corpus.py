"""Immutable corpus snapshots shared by the search-backed tools.

The docstring tool ranks a parsed corpus with BM25F and caches the result keyed
by file mtime and size. That cache used to live in five loose module globals,
which forced two things on every caller: read the globals back after loading,
and keep all five in lockstep. A single frozen :class:`Corpus` published in one
assignment removes both hazards -- there is no window in which the items, the
field counts and the statistics disagree, and callers cannot mutate what the
cache handed them.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from demetra.tools.models import CorpusStats, Field, FieldCounts
from demetra.tools.search import build_stats, score_document


FileStamp = tuple[str, int, int]


def fingerprint_directory(directory: Path) -> tuple[FileStamp, ...]:
    """Describe every ``*.py`` file under a directory by path, mtime and size.

    Args:
        directory: The directory to fingerprint. A missing directory
            fingerprints as empty.

    Returns:
        tuple[FileStamp, ...]: One stamp per file, in sorted path order.
    """
    if not directory.is_dir():
        return ()
    stamps = []
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            metadata = path.stat()
        except OSError:
            continue
        stamps.append((str(path.relative_to(directory)), metadata.st_mtime_ns, metadata.st_size))
    return tuple(stamps)


@dataclass(frozen=True)
class Corpus[T]:
    """One immutable, internally consistent view of a parsed corpus.

    Attributes:
        root: The directory the corpus was parsed from.
        fingerprint: Content stamps that invalidate the snapshot when stale.
        items: The parsed entries, aligned with ``documents`` by position.
        documents: Per-entry field counts, one tuple per configured field.
        stats: Corpus-wide statistics derived from ``documents``.
    """

    root: Path
    fingerprint: tuple[FileStamp, ...]
    items: tuple[T, ...]
    documents: tuple[tuple[FieldCounts, ...], ...]
    stats: CorpusStats


@dataclass(frozen=True)
class Ranked[T]:
    """One corpus entry that matched a query, with its score and query terms.

    Attributes:
        item: The matched entry.
        score: Its BM25F score, always greater than zero.
        terms: The normalized query terms it was matched against.
    """

    item: T
    score: float
    terms: tuple[str, ...]


def rank[T](corpus: Corpus[T], fields: Sequence[Field], terms: Sequence[str]) -> list[Ranked[T]]:
    """Score every corpus entry against the query terms, best first.

    Args:
        corpus: The snapshot to score.
        fields: Field descriptors aligned to ``corpus.documents``.
        terms: The normalized query terms.

    Returns:
        list[Ranked[T]]: Matching entries ordered by descending score.
    """
    if not terms or corpus.stats.document_count == 0:
        return []

    ranked: list[Ranked[T]] = []
    for item, document in zip(corpus.items, corpus.documents, strict=True):
        score = score_document(fields=fields, document=document, stats=corpus.stats, terms=terms)
        if score > 0:
            ranked.append(Ranked(item=item, score=score, terms=tuple(terms)))

    ranked.sort(key=lambda hit: -hit.score)
    return ranked


class CorpusCache[T]:
    """Single-slot cache that rebuilds a corpus only when its files change.

    The snapshot is published with a single attribute assignment, so a reader
    can never observe a half-updated corpus, and it is frozen so a caller
    cannot write through what it was handed.
    """

    def __init__(
        self,
        fields: Sequence[Field],
        parse: Callable[[Path], tuple[Sequence[T], Sequence[tuple[FieldCounts, ...]]]],
        fingerprint: Callable[[Path], tuple[FileStamp, ...]] = fingerprint_directory,
    ) -> None:
        """Initialize an empty cache.

        Args:
            fields: Field descriptors, used to build the corpus statistics.
            parse: Turns a directory into its entries and their field counts.
            fingerprint: Names the files whose changes invalidate the snapshot.
        """
        self._fields = tuple(fields)
        self._parse = parse
        self._fingerprint = fingerprint
        self._cached: Corpus[T] | None = None

    def get(self, root: Path) -> Corpus[T]:
        """Return the current snapshot for a directory, rebuilding it if stale.

        Args:
            root: The directory to load.

        Returns:
            Corpus[T]: A snapshot whose entries, field counts and statistics
                always describe the same generation of files.
        """
        fingerprint = self._fingerprint(root)
        cached = self._cached
        if cached is not None and cached.root == root and cached.fingerprint == fingerprint:
            return cached

        items, documents = self._parse(root)
        corpus: Corpus[T] = Corpus(
            root=root,
            fingerprint=fingerprint,
            items=tuple(items),
            documents=tuple(documents),
            stats=build_stats(fields=self._fields, documents=tuple(documents)),
        )
        self._cached = corpus
        return corpus

    def clear(self) -> None:
        """Drop the cached snapshot so the next read rebuilds it."""
        self._cached = None
