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
related:
- 2026-08-19-wiki-should-use-llm-rename.md
- 2026-08-25-mnt-187-wiki-pages-not-generated.md
- 2026-08-03-wiki-mcp-tools.md
- 2026-08-19-split-auth-linear-services-and-review-failure-handling.md
---

# Split wiki service into a subpackage

## TL;DR

Split monolithic `demetra/services/wiki.py` (1254 lines) into `demetra/services/wiki/` with six submodules behind a facade `__init__.py` re-exporting all 55 symbols. Submodules resolve shared state via `import demetra.services.wiki as service` at call time, preserving monkeypatch seams. All 728 tests + gates pass.

---

## Overview

Follows `demetra/api/` split pattern. Collided-name packages (`auth`, `linear`, `wiki`) need no `_RELOCATED_MODULES` shim — `__init__.py` is the facade. Constraint: tests patch facade state (e.g. `wiki_service.PAGES_ROOT`, `patch("demetra.services.wiki.summarize_session")`), so submodules must resolve every mutable symbol at **call time** via the facade module object.

## Step 1 — Split into submodules

`demetra/services/wiki.py` → `demetra/services/wiki/`:

- `parsing.py` — `parse_page_file`, `parse_frontmatter`, `existing_page_for_ticket`, `page_date`
- `naming.py` — `today`, `session_filename`, `infer_services`, `infer_tags`
- `facts.py` — `session_log_tail`, `git_default_branch`, `git_diff_facts`, `should_use_llm` (was `budget_exceeded`, see [[2026-08-19-wiki-should-use-llm-rename]]), `collect_session_facts`
- `index.py` — `index_entry`, `read_index`, `write_index`, `insert_pages_entry`, `prune_index_pages`, `find_topic_cluster`, `insert_cluster_entry`, `patch_index`, `cluster_for`, `regenerate_by_topic`
- `render.py` — `truncate`, `dump_frontmatter`, `render_wiki_page`, `write_page`, `write_session_wiki_page`
- `maintenance.py` — `page_tokens`, `similarity`, `answer_sweep`, `has_answer`, `dedup_pages`, `pick_survivor`, `merge_page_content`, `check_agents_drift`, `revalidate_wiki_and_agents`, `on_default_branch`, `commit_revalidation`, `run_wiki_revalidation`

Every submodule uses:

```python
import demetra.services.wiki as service
def session_log_tail(task_id: str) -> str:
    session_dir = service.LOG_DIR if service.LOG_DIR.name == "sessions" else service.LOG_DIR / "sessions"
```

Safe circular import: `service.<NAME>` only dereferenced inside function bodies.

## Step 2 — Facade `__init__.py`

**File:** `demetra/services/wiki/__init__.py` (185 lines) — keeps all constants (`FRONTMATTER_RE`, `PAGE_TYPE`/`PAGE_STATUS`, `LOG_TAIL_LINES`, `AGENTS_DRIFT_ANCHORS`, `DEDUP_SIMILARITY_THRESHOLD`, `TOPIC_KEYWORDS`, `REVALIDATION_RETRYABLE`) and re-exports every function + `run_command`/`summarize_session` + `Context`/`LinearTask`. Complete `__all__` for 55 symbols. Callers unchanged (`main.py:19`, `workflows/merge.py:12`, `tools/wiki.py:8`, tests).

## Step 3 — Verification

- All 55 original symbols reachable; 61 `service.*` refs resolve; no duplicate definitions.
- `pytest` 728 passed (59 in `test_wiki.py`, 28 in `test_wiki_tools.py`).
- `ruff`, `ruff format --check`, `ty`, `bandit`, `pre-commit` — clean.

## Test Results

`pytest` 728 passed. Full gates green.

---

## Follow-ups

None — behavior-preserving. Other flat services candidates for same treatment.

> **Consistency note (2026-08-27):** MNT-187 wiki-write move + `WikiError` contract superseded by PR #106 — `commit_and_push` now logs and continues after commit/push/PR, surfacing `WikiError` only to gate ticket status — see [[2026-08-25-mnt-187-wiki-pages-not-generated]].

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-03-wiki-mcp-tools]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]], [[2026-08-25-mnt-187-wiki-pages-not-generated]]
- External: https://linear.app/mnt/issue/MNT-81, https://linear.app/mnt/issue/MNT-104
