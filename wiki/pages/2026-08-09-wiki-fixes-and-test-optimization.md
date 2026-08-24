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

Hardened four wiki-service edge cases surfaced while exercising the freshly split subpackage (blank env paths, cluster scoring across multiple bullets, cluster insertion when the target header is the last line, unreadable page files, `answer_sweep` preamble handling) and scoped the revalidation commit to exactly the changed files. Then optimized the three slowest test files, cutting the full suite from ~13s to **729 passed in 4.60s**.

---

## Overview

Session followed the [[2026-08-07-split-wiki-service-into-subpackage]] refactor. The wiki service and runtime env helpers had latent edge-case bugs; the new `revalidation_changed_files()` seam (added to scope commits) also let `commit_revalidation` stop staging the whole `wiki/` tree. Separate profiling pass found the test suite's runtime dominated by three fixtures hitting real I/O.

## Step 1 — `env_get_path` blank-value handling

**File:** `demetra/services/runtime/utils.py:313-316`

Before, a set-but-empty env var fell through to `Path(value).resolve()`, resolving `Path("")` to CWD instead of returning the default. This is a separate bug from the MNT-147 CI failure ([[2026-08-07-mnt-147-wiki-processes-pr70-review]]), which was caused by `env_get_list` returning `[]` when `OPENCODE_REVIEW_MODELS` was unset — not by `env_get_path`:

```python
value = os.environ.get(name)
if not value or value.strip() == "":
    return default
return Path(value).resolve()
```

## Step 2 — `find_topic_cluster` aggregates across the cluster

**File:** `demetra/services/wiki/index.py:130-165`

Previously each `- [ ... ]` bullet was scored independently and the best *individual* line decided the cluster. Changed to accumulate per-header scores (`scores: dict[str, int]`) so a cluster matches when its *collected* bullets hit more terms — better placement when no single bullet is a strong match. Fallbacks preserved: highest-scoring header, else first cluster, else `### Workflow orchestration & agents`.

## Step 3 — `insert_cluster_entry` when target header is the last line

**File:** `demetra/services/wiki/index.py:168-214`

If the target cluster was the final section of INDEX.md, the loop ended via the `else` clause after the last bullet with `in_cluster = True` but nothing had been appended — the entry was silently dropped. New `else` branch appends the entry plus a trailing blank line:

```python
else:
    if in_cluster:
        lines.append(entry)
        lines.append("")
        return "\n".join(lines)
    return contents
```

## Step 4 — `answer_sweep` preamble + async file I/O

**File:** `demetra/services/wiki/maintenance.py:44-104`

Two fixes: (a) `read_text`/`write_text` moved to `asyncio.to_thread` so the blocking file I/O no longer stalls the event loop; (b) the sweep now only starts collecting entries after the first `### ` heading — intro/preamble lines above it are preserved as `preamble` and re-prepended to the rebuilt `## Open` section instead of being discarded.

## Step 5 — `parse_page_file` tolerates unreadable files

**File:** `demetra/services/wiki/parsing.py:23-27`

`path.read_text` could raise `OSError` (e.g. permission/locked file); uncaught, it aborted the whole revalidation sweep. Now caught, logged as `Skipping unreadable page: {path.name}`, and returns `None` (callers already skip `None` pages). Docstring updated to note the read failure case.

## Step 6 — Scoped revalidation commits

**File:** `demetra/services/wiki/maintenance.py:250-394`

Added `revalidation_changed_files()` — runs `git status --porcelain --untracked-files=all -- wiki/ AGENTS.md` and returns the set of changed paths. `revalidate_wiki_and_agents()` captures the set *before* the sweep, recomputes it *after*, and stores `stats["changed_files"] = sorted(after - before)`. `commit_revalidation()` now stages and commits **only** `sorted(stats["changed_files"])` instead of the broad `wiki/ AGENTS.md` pathspec; returns `None` when the set is empty (no-op commit avoided) while keeping the `index.lock` → `REVALIDATION_RETRYABLE` path. `revalidation_changed_files` added to the facade imports and `__all__` in `demetra/services/wiki/__init__.py`.

## Step 7 — Slow-test optimization

Root causes and fixes:

- `tests/test_allowlist_cli.py` seed tests: `seed_existing_users()` scanned all ~1571 users / 2520 rows in the shared dev DB with per-row queries. Fixed with a `_patch_seed_rows(email, user_id)` helper patching `demetra.services.auth.allowlist.list_user_allowlist_seed_rows` to return only the single created user's rows; both seed tests wrapped in `with _patch_seed_rows(...)`. **3.34s → 0.11s, 1.41s → 0.09s.** (Unused `AsyncMock` import removed after `ruff` flagged it.)
- `tests/test_merge_workflow.py` / `tests/test_rebase_workflow.py` `base_mocks`: the workflow `finally` block called the real `get_linear_task_by_id()` — Linear GraphQL API + DB lookup — which was never mocked. Added `patch(..., new_callable=AsyncMock)` with `return_value = None` and exposed it as `mock_get_task`. **1.57s → ~0.2s, 0.62s → ~0.2s.**

## Test Results

- Full suite: `uv run pytest tests/ -q -p no:cacheprovider` → **729 passed in 4.60s** (down from ~13s).
- `uv run ruff check .` — clean (incl. the three touched test files).
- `uv run ty check demetra/services/wiki` — clean.

---

## Follow-ups

- None. Remaining wiki follow-ups tracked on the [[2026-08-07-mnt-147-wiki-processes-pr70-review]] page.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-07-mnt-147-wiki-processes-pr70-review]], [[2026-08-09-apply-code-review-findings]]
