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
related:
- 2026-08-07-split-wiki-service-into-subpackage.md
- 2026-08-18-migrate-llm-groq-to-openrouter.md
---

# Rename wiki budget_exceeded to should_use_llm

## TL;DR

Renamed wiki gate `budget_exceeded()` → `should_use_llm()` across `demetra/services/wiki/` and `tests/test_wiki.py`. Behavior unchanged: LLM polish (`summarize_session`) runs only when `WIKI_LLM_BUDGET_FILES` (8) or `WIKI_LLM_BUDGET_LINES` (200) exceeded. All 64 wiki tests pass, ruff clean.

## Overview

Wiki pages are deterministic scaffold (`render_wiki_page`); LLM generates only TL;DR/Overview for large sessions. `budget_exceeded` read like a cost ceiling ("skip LLM when overspent") while the call site is a significance threshold ("session warrants LLM spend"), so `render.py` read backwards. Env var names (`WIKI_LLM_BUDGET_FILES`/`WIKI_LLM_BUDGET_LINES`) kept — only predicate renamed.

## Changes

- `demetra/services/wiki/facts.py:122` — `def should_use_llm(facts: dict) -> bool: return len(facts["files"]) > service.WIKI["llm_budget_files"] or facts["changed_lines"] > service.WIKI["llm_budget_lines"]`
- `demetra/services/wiki/render.py:194` — `if service.should_use_llm(facts=facts): polished_summary = await service.summarize_session(...)`
- `demetra/services/wiki/__init__.py` — facade import/`__all__` updated (alphabetical)
- `tests/test_wiki.py` — `TestBudgetExceeded` → `TestShouldUseLlm`; methods renamed to new semantics

## Test Results

- `uv run pytest tests/test_wiki.py -q` — 64 passed
- `uv run pytest tests/ -q -k "wiki or render"` — 96 passed
- `uv run ruff check demetra/services/wiki/ tests/test_wiki.py` — pass

## Follow-ups

- None

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-18-migrate-llm-groq-to-openrouter]]
