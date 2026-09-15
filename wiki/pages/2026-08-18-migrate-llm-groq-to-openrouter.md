---
title: Migrate LLM summarization from Groq to OpenRouter
date: 2026-08-18
type: implementation
status: resolved
session_id: '-'
services:
- llm
- openrouter
- groq
- workflows
- wiki
- settings
- review
- prompts
- opencode
branch: openrouter
tickets:
- MNT-168
- MNT-87
- MNT-35
- MNT-98
- MNT-41
- MNT-61
tags:
- openrouter
- groq
- llm
- migration
- summarization
- langchain
- review
- async
- parallelism
- multiagent
- cursor
- coderabbit
- llama
- parsing
- testing
- plan
- build-plan
related:
- 2026-06-04-review-summarization.md
- 2026-06-22-github-pr-description.md
- 2026-08-03-agents-md-and-wiki-consistency.md
- 2026-08-19-split-auth-linear-services-and-review-failure-handling.md
- 2026-05-25-async-review.md
- 2026-02-26-create-llm-test-script.md
- 2026-03-11-task-plan-summarization.md
---
# Migrate LLM summarization from Groq to OpenRouter

## TL;DR

Replaced Groq with OpenRouter for all LLM summarization (plan extraction, review, ticket breakdown, wiki polish, PR descriptions) via a single `build_llm()` factory over `langchain-openai` `ChatOpenAI`. New `demetra/services/llm/openrouter.py` serves all consumers; legacy `groq.py` left untouched; `OPENROUTER_*` env vars make model/endpoint a one-line config change.

---

## Overview

Old `groq.py` had 6 duplicated `ChatGroq` chains. Migration adds a provider-agnostic factory and OpenRouter module, repointing 4 consumers (`workflows/plan,review,cleanup`, `services/wiki`). Decisions: keep `groq.py`/`process_text_with_groq`, provider-specific `OPENROUTER_*` config, rename `WIKI_GROQ_BUDGET_*` → `WIKI_LLM_BUDGET_*`, AGENTS drift anchor keeps `"Groq"` + adds `"OpenRouter"`.

## Step 1 — Dependency

**File:** `pyproject.toml` — added `langchain-openai==1.4.3` (compatible with pinned `langchain-core==1.5.3`); kept `langchain-groq==1.1.3`; `uv sync` pulled `openai`/`tiktoken`/…

## Step 2 — Settings

**Files:** `demetra/library/types.py`, `demetra/settings.py` — added `OpenRouterConfig` (`api_key`, `model`, `base_url`) and `OPENROUTER` block (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL` default `openai/gpt-oss-120b`, `OPENROUTER_BASE_URL` default `https://openrouter.ai/api/v1`). `GROQ` block untouched.

## Step 3 — Factory

**File:** `demetra/services/llm/factory.py` (new)

```python
def build_llm(*, temperature: float, max_tokens: int, max_retries: int = 2) -> ChatOpenAI:
    return ChatOpenAI(model=OPENROUTER["model"], temperature=temperature, max_tokens=max_tokens,
                      max_retries=max_retries, api_key=OPENROUTER["api_key"], base_url=OPENROUTER["base_url"])
```

Replaces 6 `ChatGroq(...)` instantiations.

## Step 4 — OpenRouter module

**File:** `demetra/services/llm/openrouter.py` (new) — six functions via `build_llm()`: `extract_questions`, `summarize_review`, `process_text_with_openrouter`, `extract_plan` (keeps `PLAN_OUTPUT_MAX_CHARS = 32_000`), `summarize_session`, `generate_pr_description`. Prompts/parsers/`PLAN_HAS_QUESTIONS` gating unchanged.

## Step 5 — Repoint consumers

**Files:** `demetra/services/__init__.py`, `workflows/plan,review,cleanup.py`, `services/wiki/__init__.py`, `.env.docker.example`, `AGENTS.md`, `services/wiki/facts,render.py`

- Relocation shim gains `"openrouter": "demetra.services.llm.openrouter"` (keeps `groq`)
- 4 workflow/wiki consumers import from `openrouter`
- `AGENTS.md` external deps updated; `.env.docker.example` gains `# OpenRouter` block
- `WIKI_GROQ_BUDGET_*` → `WIKI_LLM_BUDGET_*` (settings, wiki `__all__`, budget check)

## Step 6 — Tests

**Files:** `tests/test_openrouter.py` (new, mirrors `test_groq.py` patching `build_llm`), `tests/test_wiki.py`, `tests/conftest.py:mock_openrouter`

## Test Results

- `pytest` **849 passed** (817 post-migration + URL/ticket coverage); `ruff`, `ty`, `bandit`, `pre-commit` clean; consumer modules import cleanly.

---

## Source — [[2026-05-25-async-review]]

MNT-87/35 (2026-05-25): `run_review_agents` launches opencode/cursor/coderabbit concurrently; empty commits prevented by staged-change validation. `merge_review_results` `None` handling now via `summarize_review()` in `openrouter.py`.

## Source — [[2026-06-04-review-summarization]]

Groq llama review dedup → numbered list; now via OpenRouter.

## Follow-ups

- Provision `OPENROUTER_API_KEY` in production env, remove legacy `GROQ_API_KEY` when `groq.py` retired.
- Historical wiki/audit references intentionally left untouched.

## Consistency notes

- (2026-08-19) Relocation shim deleted by MNT-170 (see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]); package is now plain marker.
- (2026-09-01) Removed circular self-link; (2026-09-02) quoted `session_id: "-"`.

## References

- Related: [[2026-06-04-review-summarization]], [[2026-06-22-github-pr-description]], [[2026-08-03-agents-md-and-wiki-consistency]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]], [[2026-05-25-async-review]], [[2026-02-26-create-llm-test-script]], [[2026-03-11-task-plan-summarization]]
- External: [MNT-168](https://linear.app/mnt/issue/MNT-168/migrate-llm-summarization-from-groq-to-openrouter)
