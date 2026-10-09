---
title: LLM-authored wiki pages and normalized frontmatter
date: 2026-10-08
type: implementation
status: resolved
session_id: ses_ee2ccebb3ffeZ1p6NUf0IS2y4j
services: [wiki, llm, settings, tests]
branch: "-"
tickets: []
tags: [wiki, llm, openrouter, frontmatter, cleanup]
related: [2026-08-19-wiki-should-use-llm-rename.md, 2026-08-25-mnt-187-wiki-pages-not-generated.md, 2026-08-07-split-wiki-service-into-subpackage.md, 2026-08-28-mnt-177-workflow-blocked-openrouter-403.md]
---

# LLM-authored wiki pages and normalized frontmatter

## TL;DR

Two changes to how the wiki is written. The deterministic render branch is gone:
`render_wiki_page`'s fixed scaffold (TL;DR / Overview / Changed files / Stat / Build plan /
Test Results) is replaced by a single LLM call that authors the whole page body, and the
`should_use_llm` budget gate that only ran that call above 8 files / 200 lines is deleted, so
every session now gets an LLM page. Separately, 93 wiki pages were normalized to
inline YAML flow lists, and the formatting rule was written down so future writes match.

## Overview

- `compose_wiki_page` (`demetra/services/llm/openrouter.py:195`) returns the full page body
  Markdown instead of the `{tldr, overview}` pair `summarize_session` used to return.
- `render_page` (`demetra/services/wiki/render.py:54`) is now 15 lines: deterministic
  frontmatter + H1 + the LLM body. Nothing else.
- Frontmatter, filename, `INDEX.md` patching and the atomic write stay in code, so pages remain
  machine-queryable and the H1 can never drift from `title`.
- A failed LLM call raises `WikiError`, which `cleanup.py` already handles by committing the
  build without a page.

## Step 1 — Why the gate existed, and why it went away

**File:** `demetra/services/wiki/facts.py`

The scaffold was the source of truth for small sessions, and `should_use_llm` used the diff
size to decide when the LLM was worth its tokens:

```python
def should_use_llm(facts: dict) -> bool:
    return (
        len(facts["files"]) > service.WIKI["llm_budget_files"]
        or facts["changed_lines"] > service.WIKI["llm_budget_lines"]
    )
```

With `WIKI_LLM_BUDGET_FILES=8` / `WIKI_LLM_BUDGET_LINES=200`, a small session got a
formulaic page and a large one got an LLM-flavoured one — so page quality was a function of
diff size rather than of what actually happened in the session. A 3-file bug fix could be a
root-cause chase worth a real narrative; a 9-file rename was mostly mechanical. Removing the
branch makes every page the same shape, which is what the `wiki-sync` skill produces by hand
and what the README now documents as the single convention.

## Step 2 — The LLM authors the body

**File:** `demetra/services/llm/openrouter.py:195`

```python
async def compose_wiki_page(
    *,
    title: str,
    page_type: str,
    ticket_text: str,
    description: str,
    build_plan: str,
    diff_summary: str,
    log_tail: str,
    linear_url: str,
    environment: SessionEnvironment | None = None,
) -> str:
```

Behaviour changes worth noting:

- No `JsonOutputParser` — the response is Markdown, passed through as `result.content`.
- `max_tokens` 1024 → 4096 and `temperature` 0.1 → 0.3; a whole page needs the budget, and the
  higher temperature is appropriate for prose rather than JSON extraction.
- `log_tail` is now actually used. `collect_session_facts` had been collecting the session log
  tail since it was introduced, and nothing consumed it.
- Failure is no longer swallowed into `{}`. It raises `WikiError`, because there is no
  scaffold left to fall back to.

**File:** `demetra/prompts/compose_wiki_page.md` (new, replaces `summarize_session.md`)

The prompt carries the per-`type` section presets from `TEMPLATE.md`, the
`anchor claims to file:line` rule, the no-markdown-tables rule, and the output contract:
start at the first `##`, no fences, always end with `## Follow-ups` and `## References`.
`linear_url` is passed so References keeps the external link the deleted scaffold emitted.

## Step 3 — Render shrinks to assembly

**File:** `demetra/services/wiki/render.py:54`

```python
def render_page(meta: dict, body: str) -> str:
    return f"{service.dump_frontmatter(meta)}\n\n# {meta['title']}\n\n{body.strip()}\n"
```

`render_wiki_page` was ~75 lines of `"\n".join([...])`. The call site
(`demetra/services/wiki/render.py:148`) awaits the LLM unconditionally and pipes the result
through `render_page`.

Dead code that only existed to feed the scaffold or the gate went with it:

- `git diff --numstat` and the `numstat` / `changed_lines` facts — `--stat` already carries the
  counts, so this removed a git subprocess per session.
- `WIKI_LLM_BUDGET_FILES` / `WIKI_LLM_BUDGET_LINES` from `demetra/settings.py`.
- `should_use_llm` and `summarize_session` from both service facades' `__all__`.

The `related` sibling list was already computed at the call site for the frontmatter, but the
prompt's output contract demands a `- Related: [[…]]` line per sibling page — so the LLM was
being asked to name pages it was never given, and could only invent them. `compose_wiki_page`
now takes `related: list[str]` and renders it into the prompt as an authoritative block:

```python
related_links = "\n".join(f"- Related: [[{Path(name).stem}]]" for name in related) or "- None"
```

The prompt states the block is exhaustive and must be reproduced verbatim, and `- None` when
there are no siblings. The `build_plan` truncation also moved from the call site into
`collect_session_facts`, next to where the fact is gathered.

## Step 4 — Frontmatter normalized across the corpus

Investigating why pages had inconsistent list styles surfaced that both forms parse
identically (`yaml.safe_load`), so nothing was broken — only inconsistent. Canonical form is
inline flow style, matching `TEMPLATE.md` and what `dump_frontmatter` emits:

```yaml
services: [api, react]          # canonical
tags: [openrouter, '403']        # numeric-looking values must be quoted
related: [2026-08-19-wiki-should-use-llm-rename.md]
branch: "-"                      # bare `-` is YAML null
```

A throwaway script rewrote only those four keys inside the leading `---` block: 93 files under
`wiki/pages` changed (+305 / −2061). It also stripped the
column-alignment padding that seven pages had copied from `TEMPLATE.md`, joined one wrapped
flow list, and quoted `403` in
[[2026-08-28-mnt-177-workflow-blocked-openrouter-403]] — that tag was parsing as an `int`,
which breaks tag string-matching in `wiki_search`.

Two pages were not frontmatter-only: `2026-09-24-mnt-219-session-log-autoscroll.md` and
`2026-09-16-mnt-205-revise-merged-environment.md` also had their now-dead `## Changed files` /
`## Stat` / `## Build plan` scaffold sections dropped from the body, since this change removes
the code that wrote them. Leaving those would have documented a rendering path that no longer
exists.

This work landed in commit `f8b627d`, separately from the LLM-composition change described in
the steps above, which is still staged.

## Test Results

- `uv run pytest tests/` — 947 passed
- `uv run ruff check .` / `ruff format --check` / `ty check` / `bandit -r demetra` — all clean

Replaced tests:

- `TestShouldUseLlm` deleted; `TestRenderWikiPage` → `TestRenderPage` (frontmatter round-trip,
  H1/body separation, no scaffold sections survive).
- `test_llm_polish_only_above_budget` + `test_cheap_run_skips_llm` →
  `test_llm_is_called_for_every_session`, `test_llm_receives_the_session_facts`,
  `test_llm_receives_sibling_pages_for_references`,
  `test_llm_failure_raises_wiki_error_and_writes_no_page`.
- `TestGitDiffFacts` trimmed for the removed `--numstat` call;
  `test_wiki_budget_reads_llm_budget_files` → `test_wiki_budget_reads_build_plan_cap`, which
  also asserts the budget keys are gone.

## Follow-ups

- `WIKI_DIFF_HUNK_CAP` is dead config — nothing reads it (already true before this change).
  Left in place; worth deleting separately.
- `PAGE_TYPE` is hardcoded to `implementation`, so the LLM only ever writes the
  implementation preset even when a session was a debug chase or an investigation. Classifying
  the type would let the prompt pick the right preset.
- `compose_wiki_page` still takes nine keyword-only params mirrored by an `input={}` literal.
  A `WikiPageFacts` dataclass would remove both the clump and the string-keyed dict plumbing.

## References

- External: -
- Related: [[2026-08-19-wiki-should-use-llm-rename]] — renamed the very gate this change deletes
- Related: [[2026-08-25-mnt-187-wiki-pages-not-generated]] — where the typed `WikiError`
  contract that `compose_wiki_page` now raises into was established
- Related: [[2026-08-07-split-wiki-service-into-subpackage]] — the `facts.py` / `render.py`
  layout this change edits
- Related: [[2026-08-28-mnt-177-workflow-blocked-openrouter-403]] — quoted as the `'403'` tag-quoting example