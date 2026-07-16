---
title:              Fix empty build plan infinite loop
date:               2026-07-16
type:               implementation
status:             resolved
session_id:         -
services:           [main, graphql, opencode]
branch:             -
tickets:            []
tags:               [workflow, session-management, error-handling, testing]
related:            [2026-07-16-empty-build-output]
---

# Fix empty build plan infinite loop

## TL;DR

Fixed a permanent workflow stall where a run failing before a plan is saved (e.g., due to a Linear API `null` response) locks the session into an unplannable state. Three fixes: (1) replan whenever `build_plan` is empty, not just when `step == 'initial'`; (2) reject malformed Linear payloads as `LinearError` instead of crashing; (3) enable fallback session ID so stuck-pending sessions can be recovered. All 472 tests pass; 11 new tests added.

---

## Overview

When a workflow run fails early (before a plan is saved), it leaves the session at `step='failed'` with an empty `build_plan`. The next run skips the plan step entirely because `main.py:55` only replans when `step == 'initial'`, so it exits with "Empty build plan, exiting." — forever. Three root causes and contributing factors prevented recovery:

1. **Replan gate is step-based, not plan-based** — `main.py:55` gates on `step == 'initial'`, but any failure sets `step='failed'` and nothing resets it.
2. **Linear API null responses crash uncaught** — `graphql_request` returned `None` for non-dict payloads (e.g., `null` body), causing `result.get(...)` calls to throw `AttributeError` before `LinearError` could catch it.
3. **Fallback session ID disabled** — `get_opencode_session_id` had its fallback commented out, so worktree-directory mismatches returned `None`, leaving `session_id=''` in the DB. The watcher's own step-reset path treats such sessions as "pending" and skips them.

All three are fixed below. Evidence: odin's DB showed 3 sessions stuck in this state (MNT-128, MNT-117, MNT-113, 4 run attempts each, max reached); all had `step='failed'` + empty `build_plan` + empty `session_id`.

---

## Step 1 — Replan on missing build_plan, not step

**File:** `main.py:55–57`

**Before:**

```python
if not context.session or context.session.step == "initial":
    if not await run_plan_step(context=context):
        return
```

**After:**

```python
if not context.session or not context.session.build_plan:
    if not await run_plan_step(context=context):
        return
```

**Why:** A session with `step='failed'` but empty `build_plan` should re-plan. The old gate (`step == 'initial'`) never re-plans a failed session because cleanup sets `step='failed'` and nothing resets it to `'initial'`. Gating on `not context.session.build_plan` instead means "if there's no plan yet, make one" — the right invariant.

---

## Step 2 — Validate Linear API response payload

**File:** `demetra/services/graphql.py:16–32`

**Before:**

```python
async with session.post(...) as response:
    response.raise_for_status()
    return await response.json()
```

**After:**

```python
async with session.post(...) as response:
    response.raise_for_status()
    data = await response.json()

if not isinstance(data, dict):
    raise LinearError(f"Linear API returned an unexpected payload: {data!r}")

return data
```

**Why:** Linear can respond 200 OK with `null` (or any non-dict JSON). Callers like `update_ticket_status` do `result.get("data", {}).get(...)`, which crashes with `AttributeError: 'NoneType' object has no attribute 'get'` — not caught by `main.py`'s except list. Now it raises `LinearError` (a `DemetraError`), so `main.py:100–104` catches it gracefully.

---

## Step 3 — Enable fallback session ID

**File:** `demetra/services/opencode.py:127–139`

**Before:**

```python
fallback_session_id = None
for session in sorted(...):
    # TODO: Think how to proceed with a worktree mistmatch
    # if not fallback_session_id:
    #     fallback_session_id = session["id"]

    if session_directory == target_directory:
        return session["id"]

print_message("Worktree mistmatch, using fallback session id", style="error")
return fallback_session_id
```

**After:**

```python
fallback_session_id = None
for session in sorted(...):
    if not fallback_session_id:
        fallback_session_id = session["id"]

    if session_directory == target_directory:
        return session["id"]

if fallback_session_id:
    print_message("Worktree mistmatch, using fallback session id", style="error")
return fallback_session_id
```

**Why:** When worktree directory doesn't match exactly, return the most-recently-updated same-titled session as a fallback. Without this, `get_opencode_session_id` returns `None`, leaving `session_id=''` in the DB. The watcher's `get_pending_session_task_ids()` treats such sessions as "pending" and skips them (`session_id == ""` is the pending marker), which suppresses the watcher's own step-reset path on future polls. Enabling the fallback lets at least some sessions get a valid ID and escape pending status.

---

## Test Results

All tests pass; 11 new tests added.

### New tests

**tests/test_entrypoints.py — TestMainReplanning:**

- `test_main_replans_when_step_failed_but_build_plan_empty` — Replans when `step='failed'` but `build_plan` is empty.
- `test_main_skips_replan_when_build_plan_already_present` — Skips replanning when a plan already exists.
- `test_main_exits_when_replan_produces_no_plan` — Exits cleanly if replanning still yields nothing.

**tests/test_graphql.py — TestGraphqlRequest:**

- `test_graphql_request_returns_dict_payload` — Valid dict payload passes through.
- `test_graphql_request_raises_linear_error_on_null_payload` — `null` payload raises `LinearError`.
- `test_graphql_request_raises_linear_error_on_list_payload` — List payload raises `LinearError`.

**tests/test_opencode.py — TestOpencodeSessionId:**

- `test_returns_exact_directory_match` — Exact directory match wins.
- `test_returns_fallback_when_no_directory_matches` — Falls back to most-recent same-titled session on mismatch.
- `test_returns_none_when_no_matching_titles` — Returns `None` when no titles match.

### Validation

```
$ uv run pytest tests/ -q
===== 472 passed in 7.78s =====

$ uv run ruff check demetra/services/graphql.py demetra/services/opencode.py main.py tests/test_entrypoints.py tests/test_graphql.py tests/test_opencode.py
All checks passed!

$ uv run ty check demetra/services/graphql.py demetra/services/opencode.py main.py
All checks passed!
```

---

## Follow-ups

- None — all three root causes and contributing factors are fixed.

## References

- Related: [[2026-07-16-empty-build-output]] — The investigation that led to these fixes.
