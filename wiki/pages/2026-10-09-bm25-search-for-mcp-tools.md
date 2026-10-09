---
title: BM25 ranking for the wiki and docstring MCP tools
date: 2026-10-09
type: implementation
status: resolved
session_id: ses_edfd46130ffe5iG0gt24tZYI1o
services: [wiki, mcp, tools]
branch: "-"
tickets: []
tags: [bm25, search, mcp, wiki, ranking, tools, caching]
related: [2026-08-03-wiki-mcp-tools.md, 2026-09-08-docstring-mcp-search.md]
---

# BM25 ranking for the wiki and docstring MCP tools

## TL;DR

`wiki_search` and `docstring_search` now rank with BM25F over cached token counts
instead of a weighted linear term count. That fixes two real defects — substring
matching (`log` matched `logging`) and the absence of IDF and length normalization —
and makes repeated searches about 20x faster, because the wiki tool no longer re-reads
and re-parses every page on every query. The design follows §5 of the
2026-09-03 gap analysis (`wiki/audits/2026-09-03-wiki-search-vs-bm25.md`).

---

## Overview

The starting point was a linear scorer with fixed field weights:

```python
score = sum(SEARCH["wiki_title_weight"] * title.count(term)      # 10x
            + SEARCH["wiki_metadata_weight"] * metadata.count(term)  # 5x
            + body.count(term)                                   # 1x
            for term in terms)
```

Three properties of that expression are defects, not simplifications:

- **`str.count` is substring matching.** `body.count("log")` hits `logging`,
  `login` and `dialog`. The query term is never required to be a token.
- **No IDF.** `mcp` and `server` contribute equally, so a term present in 60 pages
  outweighs a rare, precise one.
- **No length normalization or saturation.** Score is linear in raw hit count, so a
  500-line page outranks a focused one on bulk alone, and a term repeated 50 times
  scores 50x rather than saturating.

A fourth problem was structural: `demetra/tools/wiki.py` had no cache at all, so every
query re-globbed `wiki/pages/`, re-read all 105 files and re-parsed their YAML
frontmatter. `docstrings.py` already cached its AST index behind an mtime+size
fingerprint; the wiki tool did not.

### Storage decision

A real inverted index (SQLite FTS5) was considered and rejected. The repository is
Postgres-only with zero SQLite usage, and FTS5 would have meant either a new sidecar
artifact or an Alembic migration plus a database round-trip from the stdio MCP server,
which is otherwise purely filesystem-backed. At this corpus size the dominant cost was
re-parsing, not scoring — so caching the tokenization and improving the ranking formula
captures nearly all the benefit at a fraction of the complexity.

---

## Step 1 — Shared BM25 core in `demetra/tools/search.py`

The file previously held only `tokenize()`. It is now the shared engine both tools use,
so they cannot drift. Three frozen dataclasses carry the state:

- **`Field(weight, length_norm)`** — a document zone's boost and how strongly its length
  is normalized, from 0 (off) to 1 (full).
- **`FieldCounts(counts, length)`** — per-term counts plus the precomputed token length.
  Retaining `length` is what keeps scoring off the document text: `score_document` never
  re-walks a page body.
- **`CorpusStats`** — document count, per-field average lengths, and document frequency.

**File:** `demetra/tools/search.py:101`

```python
def build_stats(fields, documents) -> CorpusStats:
    totals = [0] * len(fields)
    document_frequency: Counter = Counter()
    for document in documents:
        present: set[str] = set()
        for index, field_counts in enumerate(document):
            totals[index] += field_counts.length
            present.update(field_counts.counts)
        document_frequency.update(present)
```

`present` is a per-document `set`, which matters: a term appearing in both a page's title
and its body must count once toward document frequency, not twice. A
`Counter.update` over the field key-views directly would have inflated `df` and silently
skewed every IDF.

**File:** `demetra/tools/search.py:130`

```python
def inverse_document_frequency(document_frequency: int, document_count: int) -> float:
    return math.log(1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5))
```

The `log(1 + ...)` form is the Lucene/Okapi variant and is used deliberately: the
uncorrected `log((N - df + 0.5) / (df + 0.5))` goes negative once a term appears in more
than half the corpus, which would let a ubiquitous term actively *subtract* from a
document's score.

**File:** `demetra/tools/search.py:146` — `score_document` is BM25F. Each field's term
frequency is normalized against that field's own average length, the normalized values
are summed under each field's boost, and saturation is applied once to the combined
value:

```python
score += idf * (weighted * (k1 + 1)) / (weighted + k1)
```

## Step 2 — Wiki tool: the cache was the real cost

**File:** `demetra/tools/wiki.py:24` — fields are declared as a module constant, so
tuning a boost is a settings change rather than a code change.

The initial plan was to rebuild the index from `services/wiki/render.py` on write. That
was wrong, and investigating it changed the design. `wiki/pages/` is not only appended to
— it also **shrinks**, because `dedup_pages` and the `wiki-archive` skill move pages into
`wiki/archive/` (27 already there). Wiki pages are additionally edited directly by agent
sessions running the `wiki-consistency`, `wiki-dedup` and `wiki-agents-file` skills, which
never call `render.py` at all. A write-triggered rebuild would have gone stale silently
and returned wrong results.

Invalidation therefore has to be derived from the filesystem, using the same
mtime+size fingerprint `docstrings.py` already had:

**File:** `demetra/tools/wiki.py:67`

```python
paths = sorted(pages_root.glob("*.md")) if pages_root.is_dir() else []
fingerprint = _fingerprint(paths=paths, pages_root=pages_root)
if pages_root == _cached_pages_root and fingerprint == _cached_fingerprint:
    return _cached_pages
```

An edit, an addition, and a page moved to `archive/` all change the fingerprint, so the
cache self-heals without any write-side hook. The root path is part of the key, which is
what keeps one test's temp directory from serving another test's cached pages.

`_load_pages` now caches three things in one pass: the parsed pages, the per-field token
counts (`_page_fields`, `demetra/tools/wiki.py:37`), and the corpus statistics.

## Step 3 — Docstring tool

The same substitution, over three zones — qualified name, source path, docstring —
declared as `DOCSTRING_FIELDS` at `demetra/tools/docstrings.py:26`. The existing
`_cached_fingerprint` guard already existed here, so the change was confined to building
`_cached_documents` and `_cached_stats` alongside `_cached_functions`, and replacing
`_score_function` with a `score_document` call.

## Step 4 — Settings and snippet matching

The four `*_weight` keys in `demetra/settings.py` were replaced by `bm25_k1` plus per-field
`*_boost` / `*_length_norm` pairs. Title and name keep `length_norm: 0.0` deliberately:
they are short and uniform across the corpus, so their length carries no signal and
normalizing would only dilute the boost. Body and docstring use the conventional `0.75`.

Snippet selection was substring-matching too, and was fixed in the same pass via
`line_hits` (`demetra/tools/search.py:193`), so the line shown under a hit is chosen by
the same token equality that ranked it.

Result scores changed type from `int` to `float` and now render with three decimals in
both tools' output.

---

## Verification on the live corpus

Measured against the real 105-page wiki:

- **Warm query — 39.758ms → 1.935ms (~20.5x).** Cold build, paid once, is 60.12ms.
- **`ses` returned 0 matches.** It previously matched every page containing `session`.
- **`confi` returned 0 matches.** It previously matched `configuration` and `configured`.
- **IDF separates equal term frequencies:** `opencode` (rare) scored 1.959 against
  `session` (common) at 1.191 for otherwise comparable hits.

## Test Results

- **`tests/test_search.py`** — new, 22 tests over the shared core: tokenization, field
  counting, per-document document frequency, IDF monotonicity, field boosts, substring
  rejection, saturation, length normalization, and `line_hits`.
- **`tests/test_wiki_tools.py`** — added `TestBm25Ranking` and `TestPageCache`. The cache
  tests pin the invalidation contract directly: a page added, a page edited in place, and
  a page deleted (the archive path) each rebuild correctly.
- **`tests/test_docstring_tools.py`** — added `TestDocstringRanking`.
- **71 passed** across the three search test files.
- **Full suite: 982 passed.** The 3–5 failures that appear intermittently are pre-existing
  and unrelated — `test_auth`/`test_waitlist_cli`/`test_allowlist` race against the
  `test_demetra` database being dropped and recreated; they reproduce on a clean tree and
  fail on a different subset each run. Two `test_utils.py` fixture errors are also
  pre-existing.
- **`ruff`, `ruff format`, `ty`, `bandit` and all pre-commit hooks pass.**

---

## Follow-ups

- Two existing pages still describe the retired algorithm and now contradict the code:
  `2026-08-03-wiki-mcp-tools.md` ("scores `10×title + 5×metadata + 1×body`") and
  `2026-09-08-docstring-mcp-search.md` (references `docstring_name_weight` /
  `docstring_path_weight`). Neither was edited here to keep this change reviewable.
- The `2026-09-03-wiki-search-vs-bm25.md` audit is a reference page describing §5 as
  unimplemented. It is now implemented and could be retired or annotated.
- `AGENTS.md:157` describes `SEARCH` as holding "shared wiki/docstring weights". That is
  still true in spirit but now means boosts and length norms plus `bm25_k1`, so the
  wording is worth tightening.
- Step 5 of the audit (stemming, and shrinking or dropping the hardcoded stop-word list
  now that IDF handles common terms) was deliberately **not** done. `logging`/`logs` and
  `configure`/`configuration` are the visible recall gaps that stemming would close.

## References

- Implementation this follows — `wiki/audits/2026-09-03-wiki-search-vs-bm25.md`
- Shared engine — `demetra/tools/search.py`
- Wiki tool — `demetra/tools/wiki.py`
- Docstring tool — `demetra/tools/docstrings.py`
- Related: [[2026-08-03-wiki-mcp-tools]]
- Related: [[2026-09-08-docstring-mcp-search]]
- External: Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond* (2009); Lucene `BM25Similarity` docs