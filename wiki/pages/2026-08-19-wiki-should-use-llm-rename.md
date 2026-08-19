---
title: Rename wiki budget_exceeded to should_use_llm
date: 2026-08-19
type: implementation
status: resolved
session_id: opencode
services: [wiki]
branch: master
tickets: []
tags: [wiki, naming, refactor, llm]
related: [2026-08-07-split-wiki-service-into-subpackage.md, 2026-08-18-migrate-llm-groq-to-openrouter.md]
---

# Rename wiki budget_exceeded to should_use_llm

## TL;DR

Renamed the wiki write-side gate `budget_exceeded()` to `should_use_llm()` across `demetra/services/wiki/` (definition, facade, call site) and `tests/test_wiki.py`. Behavior is unchanged: the LLM polish pass (`summarize_session`) still runs only when a session exceeds `WIKI_LLM_BUDGET_FILES` (8) or `WIKI_LLM_BUDGET_LINES` (200). All 64 wiki tests and ruff pass.

---

## Overview

An investigation into how workflow-end wiki pages are produced confirmed the page is a deterministic scaffold (`render_wiki_page`), with the LLM generating only the TL;DR/Overview sections for large sessions. The gate's name `budget_exceeded` read like a cost ceiling ("skip the LLM when overspent") while the call site uses it as a significance threshold ("the session warrants the LLM spend"), making `render.py` read backwards. The env var names (`WIKI_LLM_BUDGET_FILES` / `WIKI_LLM_BUDGET_LINES`) were intentionally kept — only the predicate was renamed.

## Step 1 — Rename the predicate

**File:** `demetra/services/wiki/facts.py:122`

```python
def should_use_llm(facts: dict) -> bool:
    """Decide whether a session warrants the LLM polish pass. ... """
    return (
        len(facts["files"]) > service.WIKI["llm_budget_files"]
        or facts["changed_lines"] > service.WIKI["llm_budget_lines"]
    )
```

**File:** `demetra/services/wiki/render.py:194`

```python
if service.should_use_llm(facts=facts):
    polished_summary = await service.summarize_session(...)
```

**File:** `demetra/services/wiki/__init__.py`

Facade import and `__all__` updated (alphabetical order preserved).

## Step 2 — Tests

**File:** `tests/test_wiki.py`

`TestBudgetExceeded` renamed to `TestShouldUseLlm`; methods renamed to match the new semantics (`test_under_budget_returns_false`, `test_too_many_files_returns_true`, `test_too_many_lines_returns_true`).

## Test Results

- `uv run pytest tests/test_wiki.py -q` — 64 passed
- `uv run pytest tests/ -q -k "wiki or render"` — 96 passed
- `uv run ruff check demetra/services/wiki/ tests/test_wiki.py` — all checks passed

---

## Follow-ups

- None

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-18-migrate-llm-groq-to-openrouter]]
