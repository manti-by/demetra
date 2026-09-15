---
title:              Fix empty build plan infinite loop
date:               2026-07-16
type:               implementation
status:             resolved
session_id:         "-"
services:           [main, graphql, opencode, linear, workflows, database, sessions]
branch:             "-"
tickets:            [MNT-29, MNT-39]
tags:               [workflow, session-management, error-handling, testing, linear, comment, build-plan, database, persistence]
related: [2026-02-21-add-build-plan-to-linear-task.md, 2026-02-23-save-build-plan-to-database.md, 2026-08-05-pr-creation-failure-handler.md]
---

# Fix empty build plan infinite loop

## TL;DR

Fixed a permanent stall where a run failing before plan save left `step='failed'` + empty `build_plan` → next run skipped planning (`step == 'initial'` gate) and exited forever. Three fixes: (1) replan when `build_plan` empty, not `step == 'initial'`; (2) reject non-dict Linear payloads as `LinearError`; (3) enable fallback session ID for worktree mismatches. 472 tests pass, 9 new tests added.

---

## Overview

Odin had 3 sessions stuck (MNT-128/117/113, 4 attempts each, max reached): `step='failed'` + empty `build_plan` + empty `session_id`.

## Step 1 — Replan on missing build_plan, not step

**File:** `main.py:55-57`

```python
# before
if not context.session or context.session.step == "initial":
# after
if not context.session or not context.session.build_plan:
```

Failed sessions with empty plan now correctly re-plan; previously `step='failed'` never reset to `'initial'`.

## Step 2 — Validate Linear API response

**File:** `demetra/services/graphql.py:16-32`

```python
data = await response.json()
if not isinstance(data, dict):
    raise LinearError(f"Linear API returned an unexpected payload: {data!r}")
return data
```

Linear can return 200 with `null`; callers doing `result.get(...)` crashed with `AttributeError` not caught by `main.py`. Now raises `LinearError` (`DemetraError`) and is handled gracefully.

## Step 3 — Enable fallback session ID

**File:** `demetra/services/opencode.py:127-139`

Uncommented `fallback_session_id` assignment on worktree mismatch; moved warning inside `if fallback_session_id:` guard. Without this, `session_id=''` left sessions as "pending" (watcher skips them), suppressing step-reset.

## Test Results

472 passed, `ruff`/`ty` clean. 9 new tests:

- `tests/test_entrypoints.py` (3): replan when `failed`+empty, skip when plan present, exit on still-empty replan.
- `tests/test_graphql.py` (3): dict passthrough, `null` → `LinearError`, list → `LinearError`.
- `tests/test_opencode.py` (3): exact match wins, fallback on mismatch, `None` when no title match.

---

## Source — [[2026-02-21-add-build-plan-to-linear-task]]

MNT-29 (2026-02-21): extracted build plan posted as Linear comment via `post_comment(ticket_id, comment_text)` right after planning; `posted_to_linear` flag (MNT-39) prevents double-post.

## Source — [[2026-02-23-save-build-plan-to-database]]

MNT-39 (2026-02-23): `sessions` gained `build_plan`/`posted_to_linear`; `save_session` persists plan, `upsert_pending_session` inits `build_plan=""`. Setup skips planning when plan exists. This page's `not build_plan` gate is its successor.

## Follow-ups

None.

## Consistency note (2026-08-19)

- "Cleanup sets `step='failed'`" is true for default `failure_step`; some paths now set `awaiting_input` instead (`AutoCancelledError`, `PullRequestError`, `ReviewError`). Replan gate still correct.

> **Consistency note (2026-08-24):** `demetra/services/opencode.py` → `demetra/services/agents/opencode.py`.
> **Update (2026-08-27):** `demetra/services/graphql.py` → `demetra/services/linear/graphql.py`; non-dict `LinearError` behavior unchanged.

## References

- Related: [[2026-08-05-pr-creation-failure-handler]]
