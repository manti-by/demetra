---
title: Wiki edge-case fixes and slow-test optimization
date: 2026-08-09
type: implementation
status: resolved
session_id: "-"
services: [wiki, tests, runtime]
branch: "-"
tickets: []
tags: [wiki, tests, performance, env, index, revalidation, bug]
related: [2026-08-07-mnt-147-wiki-processes-pr70-review.md, 2026-08-07-split-wiki-service-into-subpackage.md, 2026-08-09-apply-code-review-findings.md]
---

# Wiki edge-case fixes and slow-test optimization

## TL;DR

Hardened four wiki-service edge cases from the subpackage split (blank env paths, cluster scoring, last-header insertion, unreadable files, `answer_sweep` preamble) and scoped revalidation commits to changed files. Then cut the suite from ~13s to **729 passed in 4.60s** by fixing three slow fixtures.

---

## Overview

Follow-up to [[2026-08-07-split-wiki-service-into-subpackage]]; also fixes the new `revalidation_changed_files()` seam so `commit_revalidation` stages only changed files, not the whole `wiki/` tree.

## Step 1 — `env_get_path` blank-value handling

**File:** `demetra/services/runtime/utils.py:313-316` — empty env var resolved `Path("")` to CWD instead of returning default (distinct from `env_get_list` CI bug in [[2026-08-07-mnt-147-wiki-processes-pr70-review]]).

```python
value = os.environ.get(name)
if not value or value.strip() == "":
    return default
return Path(value).resolve()
```

## Step 2 — `find_topic_cluster` aggregates scores

**File:** `demetra/services/wiki/index.py:130-165` — was scoring each bullet independently; now accumulates per-header (`scores: dict[str,int]`) so a cluster matches on collected bullets. Fallbacks: best header → first cluster → `Workflow orchestration & agents`.

## Step 3 — `insert_cluster_entry` at last line

**File:** `demetra/services/wiki/index.py:168-214` — when target header was final section, entry was silently dropped. New `else` appends `entry + ""` when `in_cluster` is true.

```python
else:
    if in_cluster:
        lines.append(entry); lines.append("")
        return "\n".join(lines)
```

## Step 4 — `answer_sweep` preamble + async I/O

**File:** `demetra/services/wiki/maintenance.py:44-104` — (a) `read_text`/`write_text` via `asyncio.to_thread` to avoid event-loop stall; (b) sweep starts only after first `### ` heading, preserving preamble lines above it.

## Step 5 — `parse_page_file` tolerates unreadable files

**File:** `demetra/services/wiki/parsing.py:23-27` — `OSError` on `read_text` now caught, logged `Skipping unreadable page: {path.name}`, returns `None`.

## Step 6 — Scoped revalidation commits

**File:** `demetra/services/wiki/maintenance.py:250-394`, `demetra/services/wiki/__init__.py`

Added `revalidation_changed_files()` (`git status --porcelain --untracked-files=all -- wiki/ AGENTS.md` → changed paths set). `revalidate_wiki_and_agents()` captures before/after, stores `stats["changed_files"] = sorted(after - before)`. `commit_revalidation()` stages only that set; returns `None` if empty; keeps `index.lock` → `REVALIDATION_RETRYABLE`.

## Step 7 — Slow-test optimization

- `tests/test_allowlist_cli.py` — `seed_existing_users()` scanned ~1571 users/2520 rows. Added `_patch_seed_rows` helper patching `list_user_allowlist_seed_rows` to single user → **3.34s→0.11s, 1.41s→0.09s**.
- `tests/test_merge_workflow.py` / `test_rebase_workflow.py` — `finally` called real `get_linear_task_by_id` (Linear+DB). Added `patch(..., AsyncMock)` returning `None` → **1.57s/0.62s→~0.2s**.

## Test Results

- `pytest -q -p no:cacheprovider` → **729 passed in 4.60s** (was ~13s).
- `ruff check`, `ty check demetra/services/wiki` — clean.

---

## Follow-ups

None.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-07-mnt-147-wiki-processes-pr70-review]], [[2026-08-09-apply-code-review-findings]]
