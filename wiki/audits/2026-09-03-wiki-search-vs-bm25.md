---
title: Wiki Search vs BM25 — Gap Analysis of the Current MCP Ranking Algorithm
date: 2026-09-03
type: investigation
status: reference
session_id: manual-research
services: [wiki, tools, mcp]
branch: -
tickets: []
tags: [wiki, search, bm25, mcp, ranking, tf-idf, investigation]
related:
  - 2026-08-03-wiki-mcp-tools.md
  - 2026-08-03-agents-md-and-wiki-consistency.md
---

# Wiki Search vs BM25 — Gap Analysis of the Current MCP Ranking Algorithm

## TL;DR

`wiki_search` in `demetra/tools/wiki.py:131` is a weighted linear-TF scorer (`10× title + 5× metadata + 1× body` per `str.count`) with stop-word filtering — roughly **20–30% of BM25**. It shares tokenization and term-frequency with BM25 but is missing the three pillars that define BM25: IDF, length normalization, and term saturation (`k1`/`b`, `N`, `avgdl`, `df`). For the current ~80 page wiki the practical gap is small, but ranking degrades on long pages or common-term queries. A drop-in BM25/BM25F migration is ~30 lines and requires one corpus-stats pre-pass.

---

## 1. Current algorithm (`demetra/tools/wiki.py`)

**File:** `demetra/tools/wiki.py:1-400` · **Tests:** `tests/test_wiki_tools.py:96-119`

### 1.1 Pipeline

```
query → _tokenize() → _score_page() per page → sort desc → _extract_snippets()
```

### 1.2 Tokenization — `wiki.py:53,98`

```python
TERM_RE = re.compile(r"[a-z0-9][a-z0-9_.\-]*")  # wiki.py:53
STOP_WORDS = frozenset(( "a","an","and", ... "with", ))  # 28 words, wiki.py:22
def _tokenize(query: str) -> list[str]:
    return [t for t in TERM_RE.findall(query.lower()) if t not in STOP_WORDS and len(t) > 1]
```

Lowercases, keeps dotted/dashed tokens (`mcp_server.py`, `on_list_tools`), drops the 28 stop words and single-char tokens. Reasonably close to BM25's typical tokenizer (without stemming).

### 1.3 Scoring — `wiki.py:131`

```python
def _score_page(page, terms) -> int:
    title    = str(page["meta"].get("title") or "").lower()
    metadata = _metadata_text(page["meta"])   # tags+services+tickets+type lowercased, wiki.py:110
    body     = page["body"].lower()
    score = 0
    for term in terms:
        score += TITLE_WEIGHT * title.count(term)      # 10 ×, wiki.py:19
        score += METADATA_WEIGHT * metadata.count(term) # 5 ×, wiki.py:20
        score += body.count(term)                       # 1 ×
    return score
```

| Constant | Value | Source |
|---|---|---|
| `TITLE_WEIGHT` | `10` | `wiki.py:19` |
| `METADATA_WEIGHT` | `5` | `wiki.py:20` |
| `BODY_WEIGHT` | `1` (implicit) | `wiki.py:150` |
| `DEFAULT_SEARCH_LIMIT` | `5` | `wiki.py:14` |
| `MAX_SEARCH_RESULTS` | `20` | `wiki.py:15` |

Search itself — `wiki.py:181`:

```python
def _search_pages(pages_root, query, limit):
    terms = _tokenize(query)
    if not terms: return []
    results = []
    for page in _load_pages(pages_root):       # sorted glob, wiki.py:56
        score = _score_page(page, terms)
        if score > 0: results.append({"page": page, "score": score, "terms": terms})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]
```

No corpus-level state — each page scored in isolation.

### 1.4 Snippet extraction — `wiki.py:154`

Line-granular, not used in ranking: scores lines by `sum(line.count(term))`, picks top `MAX_SNIPPETS=3`, returns in document order truncated to `SNIPPET_LENGTH=200`. Ranking and snippet selection are decoupled.

### 1.5 Notable quirks

- **Substring, not token count.** `str.count(term)` matches inside words: `title.count("mcp")` hits `mcp_server`, `body.count("server")` hits `serverless`. BM25 counts discrete tokens.
- **Linear TF.** 10 hits = 10× the score of 1 hit. No saturation.
- **Stop-word edge case tested:** `wiki._search_pages(pages_root, "the and of", 10) == []` — `tests/test_wiki_tools.py:114`.

---

## 2. BM25 standard

Canonical Robertson / Spärck Jones BM25 per query term `qi` in document `D`:

```
score(D,Q) = Σ IDF(qi) · ( tf(qi,D) · (k1 + 1) ) / ( tf(qi,D) + k1 · (1 - b + b · |D|/avgdl) )

IDF(qi) = log( (N - n(qi) + 0.5) / (n(qi) + 0.5) + 1 )   # Lucene/Okapi variant
```

| Symbol | Meaning | Typical value |
|---|---|---|
| `tf(qi,D)` | term frequency in `D` (token count) | — |
| `N` | corpus size (number of docs) | — |
| `n(qi)` | docs containing `qi` (`df`) | — |
| `|D|` | doc length (tokens) | — |
| `avgdl` | average `|D|` over corpus | — |
| `k1` | saturation | `1.2–2.0` |
| `b` | length-normalization strength | `0.75` |

**BM25F** (fielded variant, for `title`/`metadata`/`body`) applies the same formula per field with per-field `avgdl` and a field `boost`.

---

## 3. Gap analysis

| Dimension | Current `wiki.py` | BM25 / BM25F | Distance |
|---|---|---|---|
| **Tokenization** | `TERM_RE` + 28 stop words, `len>1`, lowercase, keeps `a.b`, `a-b`, `a_b` | Same + Porter/snowball stemming, often larger stop list or no stop list (IDF handles it) | **Small** — add stemming only if recall on `logging`/`logs` matters. |
| **TF definition** | `str.count(term)` substring on raw lowercased text | Token-count on tokenized text (`body.split` / analyzer) | **Medium — bug.** Inflates scores via substring hits. |
| **TF saturation** | Linear: `score ∝ tf` (`10·tf_title + 5·tf_meta + 1·tf_body`) | Asymptotic: `tf·(k1+1)/(tf+k1·(...))` → caps at `k1+1` | **Major.** Long pages with 10× repeat dominate. |
| **IDF** | None — `mcp` and `server` weight equally | `log((N-n+0.5)/(n+0.5)+1)` — rare terms dominate | **Missing.** Root cause of poor discrimination on common terms. Requires `N` and `df[term]` built from `_load_pages()`. |
| **Length normalization** | None | `b·|D|/avgdl` penalizes long docs | **Missing.** Longer wiki pages (e.g. this audit vs a short `debug` page) win linearly. Needs `avgdl` + `|D|` per doc/field. |
| **Field weighting** | Hardcoded `10 / 5 / 1` | BM25F: per-field `boost` + per-field length norm (`avgdl_title`, `avgdl_body`, ...) | **Ad-hoc.** Fixed weights are the only BM25F-like idea, but without length norm per field. |
| **Corpus statistics** | Stateless per-page loop, no globals | Requires one pre-pass: `N`, `avgdl`, `df` map | **Missing.** The architectural gap — current `_search_pages` cannot compute IDF without a first pass. |
| **Ranking vs snippets** | Ranking on `title/meta/body` counts; snippets ranked separately by line hits | Unified — same `tf`/`IDF` drives both (or snippets via passage BM25) | **Decoupled.** Not wrong, but snippet line chosen by raw `count` inherits the same substring/lack-of-IDF bias. |

**Summary distance:** ~20–30% of BM25. The shared slice is "tokenize → TF → field boost → sort". The missing slice is everything that makes BM25 robust to corpus frequency and document length.

---

## 4. How far in practice

| Corpus | Impact of missing IDF/length-norm |
|---|---|
| Current wiki (~70–80 pages, short bodies ≤200 lines) | **Low–moderate.** Small `N` and short docs mask the gap; title boost (`10×`) usually surfaces the right page as `tests/test_wiki_tools.py:105` asserts. Common-term queries (`"the logging pipeline mcp server"`, `tests/test_wiki_tools.py:117`) still rank but order is brittle. |
| Larger wiki (200+ pages) or long `investigation` pages | **High.** Without IDF, a `server` mention in 60 pages outranks a rare `opencode` hit. Without length norm + saturation, a 500-line `sdd-comparison.md` outranks a focused `debug` page with 1 precise title hit. |

---

## 5. Upgrade path (incremental, no deps)

All changes local to `demetra/tools/wiki.py`; `tests/test_wiki_tools.py` expectations on ordering still hold for the current fixtures (title hit still wins).

1. **Fix TF to token-count** — tokenize `title`/`metadata`/`body` with `TERM_RE` and count token equality instead of `str.count`. Removes substring inflation.
2. **Pre-pass for corpus stats** — in `_search_pages`, after `_load_pages`, build `N = len(pages)`, `doc_lens = [len(tokenize(doc))]`, `avgdl = mean(doc_lens)`, `df = Counter(term → docs containing term)`.
3. **Add BM25 core** — replace `wiki.py:146-151` loop with:
   ```python
   # k1=1.2, b=0.75
   idf = math.log((N - df[term] + 0.5) / (df[term] + 0.5) + 1)
   score += idf * (tf * (k1+1)) / (tf + k1 * (1 - b + b * dl / avgdl))
   ```
4. **BM25F (optional)** — compute `avgdl` per field, score each field separately, weight by `boost_title=2.0, boost_meta=1.2, boost_body=1.0` (tuned to preserve current `10/5/1` intent but length-normalized).
5. **Consider stemming/stop-word relaxation** — IDF already down-weights frequent terms; the hardcoded `STOP_WORDS` can shrink or be removed once IDF is live.

> Tip: `rank-bm25` on PyPI is a single-file pure-Python reference if a vendored impl is preferred over hand-rolling.

---

## Follow-ups

- None — reference audit. Implement §5 if wiki grows past ~150 pages or ranking complaints appear.

## References

- Current implementation — [`demetra/tools/wiki.py:19-20,53,98,110,131,154,181`](demetra/tools/wiki.py), [`demetra/services/wiki/__init__.py`](demetra/services/wiki/__init__.py)
- Tests — [`tests/test_wiki_tools.py:96-119,121-137`](tests/test_wiki_tools.py)
- Wiki conventions — [`wiki/README.md`](wiki/README.md), [`wiki/TEMPLATE.md`](wiki/TEMPLATE.md), [`wiki/INDEX.md`](wiki/INDEX.md)
- Prior wiki MCP page — [[2026-08-03-wiki-mcp-tools]]
- Audit markup example this file follows — [`wiki/audits/2026-08-20-sdd-comparison.md`](wiki/audits/2026-08-20-sdd-comparison.md)
- BM25 original — Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond* (2009); Lucene `BM25Similarity` docs
