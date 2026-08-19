---
title: Migrate LLM summarization from Groq to OpenRouter
date: 2026-08-18
type: implementation
status: resolved
session_id: "-"
services: [llm, openrouter, groq, workflows, wiki, settings]
branch: openrouter
tickets: [MNT-168]
tags: [openrouter, groq, llm, migration, summarization, langchain]
related: [2026-06-04-review-summarization.md, 2026-06-22-github-pr-description.md, 2026-08-03-agents-md-and-wiki-consistency.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md]
---

# Migrate LLM summarization from Groq to OpenRouter

## TL;DR

Replaced the Groq-backed LLM service with OpenRouter for plan extraction, review
summarization, ticket breakdown, wiki polish and PR descriptions — removing Groq
vendor lock-in behind a single provider. A new `demetra/services/llm/openrouter.py`
module (backed by a single `build_llm()` factory over `langchain-openai`
`ChatOpenAI` + `OPENROUTER_BASE_URL`) now serves all workflow consumers; the
legacy `demetra/services/llm/groq.py` was left untouched. Changing the model or
endpoint is now a one-line config change via `OPENROUTER_*` env vars.

---

## Overview

The old `groq.py` had 6 LangChain `ChatGroq` chains (`prompt | llm | parser`)
with duplicated model instantiation. The migration adds a provider-agnostic
factory and a new OpenRouter-backed module, then repoints all four consumers
(`workflows/plan.py`, `workflows/review.py`, `workflows/cleanup.py`,
`services/wiki/__init__.py`). Per the requester's decisions: `groq.py` and
`process_text_with_groq` are kept as-is, config is provider-specific
(`OPENROUTER_*`), `WIKI_GROQ_BUDGET_*` was renamed to `WIKI_LLM_BUDGET_*`, and
the AGENTS drift anchor keeps `"Groq"` and adds `"OpenRouter"`.

## Step 1 — Add the OpenRouter dependency

**File:** `pyproject.toml`

Added `langchain-openai==1.4.3` (the newest release compatible with the pinned
`langchain-core==1.5.3`; `1.5.x` needs `langchain-core>=1.5.4`). Kept
`langchain-groq==1.1.3` so the legacy module stays importable. `uv sync` pulled
in `openai`, `tiktoken`, `jiter`, `tqdm` transitively.

## Step 2 — Provider config in settings

**File:** `demetra/library/types.py`, `demetra/settings.py`

Added `OpenRouterConfig` TypedDict (`api_key`, `model`, `base_url`) and an
`OPENROUTER` settings block reading `OPENROUTER_API_KEY`,
`OPENROUTER_MODEL` (default `openai/gpt-oss-120b`, parity with the old Groq
default) and `OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`).
The `GROQ` block stays untouched.

## Step 3 — Single LLM factory

**File:** `demetra/services/llm/factory.py` (new)

```python
def build_llm(*, temperature: float, max_tokens: int, max_retries: int = 2) -> ChatOpenAI:
    return ChatOpenAI(
        model=OPENROUTER["model"], temperature=temperature, max_tokens=max_tokens,
        max_retries=max_retries, api_key=OPENROUTER["api_key"], base_url=OPENROUTER["base_url"],
    )
```

`ChatOpenAI` accepts `max_tokens` via its aliased field. Replaces the 6
duplicated `ChatGroq(model=GROQ["model"], ...)` instantiations so a model or
endpoint change is a one-line config change.

## Step 4 — New OpenRouter module

**File:** `demetra/services/llm/openrouter.py` (new)

Six functions migrated from `groq.py` semantics, all via `build_llm()`:
`extract_questions`, `summarize_review`, `process_text_with_openrouter`,
`extract_plan` (keeps the `PLAN_OUTPUT_MAX_CHARS = 32_000` truncation),
`summarize_session`, `generate_pr_description`. Prompts, parsers
(`JsonOutputParser`, `NumberedListOutputParser`) and the `PLAN_HAS_QUESTIONS`
gating are unchanged. `groq.py` itself is not modified.

## Step 5 — Repoint consumers and docs

**Files:** `demetra/services/__init__.py`, `workflows/plan.py`,
`workflows/review.py`, `workflows/cleanup.py`, `services/wiki/__init__.py`,
`.env.docker.example`, `AGENTS.md`, `services/wiki/facts.py`,
`services/wiki/render.py`

- Relocation shim `demetra/services/__init__.py` gains
  `"openrouter": "demetra.services.llm.openrouter"` (keeps the `groq` entry)
- All four workflow/wiki consumers import from `demetra.services.llm.openrouter`
- `AGENTS.md` external deps: OpenRouter entry (anchor
  `demetra/services/llm/openrouter.py`), Groq marked legacy
- `.env.docker.example` gains the `# OpenRouter` block
- `WIKI_GROQ_BUDGET_FILES` / `WIKI_GROQ_BUDGET_LINES` renamed to
  `WIKI_LLM_BUDGET_FILES` / `WIKI_LLM_BUDGET_LINES` (settings, wiki facade
  `__all__`, `facts.py` budget check, render docstring)

## Step 6 — Tests

**Files:** `tests/test_openrouter.py` (new), `tests/test_wiki.py`,
`tests/conftest.py`

- New `tests/test_openrouter.py` mirrors `test_groq.py` (signatures, empty-input
  short-circuit, 32k plan truncation, `summarize_session` JSON handling) but
  patches `demetra.services.llm.openrouter.build_llm` instead of `ChatGroq`
- `conftest.py` gains a `mock_openrouter` fixture (keeps `mock_groq`)
- `test_wiki.py`: `infer_services` covers `openrouter.py`; drift-anchor tests
  assert both `Groq` and `OpenRouter`; budget constants renamed

## Test Results

- `uv run pytest tests/` — **849 passed** (817 after the migration, plus URL
  validation and ticket payload coverage added from the CodeRabbit review)
- `uv run ruff check .` — all checks passed
- `uv run ty check` — all checks passed
- `uv run bandit -c pyproject.toml .` — 0 issues
- `uv run pre-commit run --all-files` — all hooks passed
- Smoke: all consumer modules (`plan`, `review`, `cleanup`, `wiki`, `app`)
  import cleanly

---

## Follow-ups

- Provision `OPENROUTER_API_KEY` in the production `.env` / `.env.docker` and
  remove the now-legacy `GROQ_API_KEY` once `groq.py` is retired
- Historical wiki pages and the `wiki/audits/2026-02-23-questions-extraction/`
  benchmark script still reference Groq — intentionally left untouched

## Consistency note (2026-08-19)

- The relocation shim (`_RelocatedFinder` / `_RelocatedLoader` in `demetra/services/__init__.py`) described in Step 5 was subsequently deleted by the 2026-08-19 work (MNT-170, see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]). The package is now a plain docstring marker.

## References

- Related: [[2026-06-04-review-summarization]] (original Groq review summarization), [[2026-06-22-github-pr-description]] (original Groq PR description), [[2026-08-03-agents-md-and-wiki-consistency]] (wiki Groq budget rename), [[2026-08-19-split-auth-linear-services-and-review-failure-handling]] (review-error routing)
- External: [MNT-168](https://linear.app/mnt/issue/MNT-168/migrate-llm-summarization-from-groq-to-openrouter)
