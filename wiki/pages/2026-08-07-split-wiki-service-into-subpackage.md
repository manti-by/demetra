---
title: Split wiki service into a subpackage
date: 2026-08-07
type: implementation
status: resolved
session_id: "-"
services: [wiki]
branch: "-"
tickets: []
tags: [wiki, refactor, subpackage, facade]
related: [2026-08-03-wiki-mcp-tools.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md, 2026-08-19-wiki-should-use-llm-rename.md, 2026-08-25-mnt-187-wiki-pages-not-generated.md]
---

# Split wiki service into a subpackage

## TL;DR

Split the monolithic `demetra/services/wiki.py` (1254 lines) into a `demetra/services/wiki/` package: six submodules (`parsing`, `naming`, `facts`, `index`, `render`, `maintenance`) behind a facade `__init__.py` that re-exports all 55 original symbols. Submodules access shared state via `import demetra.services.wiki as service` + `service.<NAME>` at call time, so existing monkeypatch/patch test seams keep working unchanged. All 728 tests and full gate suite pass.

---

## Overview

The refactor splits large flat service modules into subpackages while keeping a stable public surface. Collided-name packages (`auth`, `linear`, `wiki`) need no `_RELOCATED_MODULES` entry and no shim — the package `__init__.py` is the facade. Two prior splits set the template: `demetra/api/` (MNT-81) and the `_RelocatedFinder`/`_RelocatedLoader` mechanism in `demetra/services/__init__.py`.

Key design constraint: tests patch module-level state through the facade — e.g. `tests/conftest.py:43` patches `wiki_service.PAGES_ROOT`, and `tests/test_wiki.py:542,554` use `patch("demetra.services.wiki.summarize_session")`. Submodules must therefore resolve every mutable symbol at **call time** through the facade module object, never via direct imports that would freeze the binding.

## Step 1 — Split into submodules

**File:** `demetra/services/wiki.py` → `demetra/services/wiki/`

Extracted the module body into six submodules grouped by concern, moving module-level constants into the facade:

- `parsing.py` — `parse_page_file`, `parse_frontmatter`, `existing_page_for_ticket`, `page_date`
- `naming.py` — `today`, `session_filename`, `infer_services`, `infer_tags`
- `facts.py` — `session_log_tail`, `git_default_branch`, `git_diff_facts`, `should_use_llm` (renamed from `budget_exceeded`, see [[2026-08-19-wiki-should-use-llm-rename]]), `collect_session_facts`
- `index.py` — `index_entry`, `read_index`, `write_index`, `insert_pages_entry`, `prune_index_pages`, `find_topic_cluster`, `insert_cluster_entry`, `patch_index`, `cluster_for`, `regenerate_by_topic`
- `render.py` — `truncate`, `dump_frontmatter`, `render_wiki_page`, `write_page`, `write_session_wiki_page`
- `maintenance.py` — `page_tokens`, `similarity`, `answer_sweep`, `has_answer`, `dedup_pages`, `pick_survivor`, `merge_page_content`, `check_agents_drift`, `revalidate_wiki_and_agents`, `on_default_branch`, `commit_revalidation`, `run_wiki_revalidation`

Every submodule starts with `import demetra.services.wiki as service` and reads shared symbols through it:

```python
import demetra.services.wiki as service

def session_log_tail(task_id: str) -> str:
    ...
    session_dir = service.LOG_DIR if service.LOG_DIR.name == "sessions" else service.LOG_DIR / "sessions"
    tail: deque[str] = deque(maxlen=service.LOG_TAIL_LINES)
```

This resolves the circular import safely: when `demetra.services.wiki` is still partially initialized mid-import, submodules only dereference `service.<NAME>` inside function bodies, never at module scope.

## Step 2 — Facade `__init__.py`

**File:** `demetra/services/wiki/__init__.py` (185 lines, down from 1254)

Keeps all constants verbatim (`FRONTMATTER_RE`, `BARE_DASH_RE`, `PAGE_LINK_RE`, `PAGE_TYPE`/`PAGE_STATUS`, `LOG_TAIL_LINES`, `AGENTS_DRIFT_ANCHORS`, plus `DEDUP_SIMILARITY_THRESHOLD`, `TOPIC_KEYWORDS`, `REVALIDATION_RETRYABLE`) and re-exports every function from the submodules plus `run_command`/`summarize_session` (via the `openrouter`/`subprocess` modules) and `Context`/`LinearTask` from `library.models`. A complete `__all__` lists all 55 original symbols.

Callers are unaffected — they import from the facade exactly as before: `main.py:19`, `demetra/workflows/merge.py:12`, `demetra/workflows/rebase.py:11`, `demetra/tools/wiki.py:8`, `tests/test_wiki.py`, `tests/conftest.py`.

## Step 3 — Verification

- Symbol inventory diff vs the staged original: all 55 module-level names defined in the 1254-line original are reachable through the facade; no dangling `service.*` references across the submodules (61 distinct refs, all resolve); no duplicate definitions between submodules.
- `uv run pytest tests/` → 728 passed (incl. 59 in `test_wiki.py`, 28 in `test_wiki_tools.py`).
- `uv run ruff check .`, `ruff format --check .`, `ty check`, `bandit -c pyproject.toml .`, `pre-commit run --all-files` — all pass.

## Test Results

`pytest tests/` — 728 passed. Full gate suite green.

---

## Follow-ups

- None — split is behavior-preserving and verified. Remaining flat services (e.g. `settings.py`, `utils.py`) are candidates for the same treatment if they grow.

> **Consistency note (2026-08-27, Consistency Agent):** MNT-187 initially moved the session wiki write from `main.py`'s `finally` block into `commit_and_push` (before commit, targeting the worktree `wiki/` root) and made failures raise `WikiError` instead of being swallowed. This raise-on-failure contract was superseded by PR #106 — `commit_and_push` now logs the wiki failure and continues after successful commit, push, and PR creation, only then surfacing `WikiError` to gate the ticket status — see [[2026-08-25-mnt-187-wiki-pages-not-generated]].

## References

- Related: [[2026-08-03-wiki-mcp-tools]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]] (follow-up subpackage split), [[2026-08-25-mnt-187-wiki-pages-not-generated]]
- External: https://linear.app/mnt/issue/MNT-81 (prior api split), https://linear.app/mnt/issue/MNT-104 (services refactor)
