---
title: Fix code-review findings on step/status refactor
date: 2026-07-16
type: implementation
status: resolved
session_id: e6a4e432-a337-46a5-8e3a-a027d7cb0cdd
services: [main, api, database, workflows, linear, sessions]
branch: "-"
tickets: [MNT-37, MNT-63]
tags: [sessions, step, status, code-review, database, refactor, modules, workflow, user-scoping, task-status, migration]
related: [2026-02-23-refactor-workflow-into-modular-steps.md, 2026-04-02-link-user-tasks-sessions.md, 2026-07-16-simplify-session-logging-setup.md, 2026-08-05-pr-creation-failure-handler.md, 2026-08-25-mnt-187-wiki-pages-not-generated.md]
---

# Fix code-review findings on step/status refactor

## TL;DR

Ran `/code-review` against the working-tree diff that migrated session tracking from a `status`
column/concept to a granular `step` column (initial/plan/build/review/lint/test/push/completed/failed).
It surfaced 4 verified findings — a drifting duplicate step enum, a `status`/`step` naming
conflation in the public API, a stale hardcoded return value in `upsert_pending_session`, and two
undocumented `ON CONFLICT` clauses that diverge in intent. All 4 were fixed; 473 tests, `ruff`, and
`ty check` are clean.

---

## Overview

The reviewed diff introduced `sessions.step` as the real source of truth for workflow progress and
started filtering the `GET /api/v1/sessions` endpoint by it, but left several loose ends: a second
hand-maintained copy of the step vocabulary, an API surface still named after the old `status`
concept, and an upsert whose SQL was fixed to preserve `step` on conflict without its Python return
value following suit.

## Step 1 — Unify the step vocabulary

`demetra/library/models.py` already defined `StepType` as the canonical step enum, but
`demetra/api/sessions.py` had its own hardcoded `VALID_STATUSES` set that had already drifted —
missing `"failed"` from `StepType` even though `demetra/workflows/cleanup.py` sets `step="failed"`.

**File:** `demetra/library/models.py:8`
```python
# before
StepType = Literal["initial", "plan", "build", "review", "lint", "test", "push", "completed"]
# after
StepType = Literal["initial", "plan", "build", "review", "lint", "test", "push", "completed", "failed"]
```

**File:** `demetra/api/sessions.py:14`
```python
# before
VALID_STATUSES = {"initial", "plan", "build", "review", "lint", "test", "push", "completed", "failed"}
# after
VALID_STEPS = set(get_args(StepType))
```

## Step 2 — Rename `status` to `step` end-to-end

The `/api/v1/sessions` query param, error message, and `get_sessions()` kwarg all still said
`status` even though the diff made the actual filter operate on the `step` column — the docstring
even said "current step" for a param literally named `status`.

**File:** `demetra/api/sessions.py`
```python
# before
status: str | None = Query(default=None)
...
if status is not None and status not in VALID_STATUSES:
    raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {...}")
sessions = await get_sessions(user_id=user.id, status=status)
# after
step: str | None = Query(default=None)
...
if step is not None and step not in VALID_STEPS:
    raise HTTPException(status_code=400, detail=f"Invalid step. Must be one of: {...}")
sessions = await get_sessions(user_id=user.id, step=step)
```

**File:** `demetra/services/database.py:349`
```python
async def get_sessions(user_id: str, step: str | None = None) -> list[dict]:
    query = select(sessions).where(sessions.c.user_id == user_id)
    if step:
        query = query.where(sessions.c.step == step)
```

Verified no frontend consumer (`react/src/services/api.ts`) or other caller passed the `status`
query param, so the rename was safe. Updated `tests/test_session_logging.py`'s
`test_list_sessions_filter_by_status` → `test_list_sessions_filter_by_step` and
`test_list_sessions_invalid_status` → `test_list_sessions_invalid_step` to match.

## Step 3 — Make `upsert_pending_session`'s return value match the DB

The diff fixed the SQL (`step = sessions.step` on conflict, preserving progress instead of
resetting it to `"initial"`), but the function still constructed its returned `Session` with a
hardcoded `step="initial"`, regardless of what was actually persisted. Latent today (no caller
reads `.step` off the return value), but a real inconsistency the diff introduced.

**File:** `demetra/services/database.py:84-146`
```python
# before: no RETURNING clause, return value hardcodes step="initial"
await connection.execute(text("""... ON CONFLICT ... step = sessions.step ..."""), {...})
await connection.commit()
return Session(..., step="initial", ...)

# after: RETURNING the real row, return value reflects actual persisted step
result = await connection.execute(
    text("""... ON CONFLICT ... step = sessions.step ...
    RETURNING task_id, name, session_id, build_plan, posted_to_linear, step, project_id,
              user_id, run_attempts, pr_link, linear_link, created_at, updated_at"""),
    {...},
)
row = result.fetchone()
await connection.commit()
assert row is not None
return Session(task_id=row.task_id, ..., step=row.step or "initial", ...)
```

`ty check` initially flagged `row` as `Row | None` (fetchone()'s type) — added the guard so the
type checker is satisfied. (Note: a subsequent edit outside this session replaced the `assert`
with an explicit `if row is None: raise BaseException` check — see current file state.)

## Step 4 — Document the two divergent `ON CONFLICT` clauses

`upsert_pending_session` and `save_session` both have near-identical
`INSERT ... ON CONFLICT (task_id) DO UPDATE` blocks for the `sessions` table, but handle `step`
differently with no comment explaining it's intentional:

- `upsert_pending_session` (the idempotent "create if missing" entry point) must **never regress**
  an in-progress session's step back to `"initial"` on re-upsert.
- `save_session` (called right after the plan step completes) must **always advance** step.

**File:** `demetra/services/database.py:99-107`
```python
step = sessions.step,  -- step is owned by update_session_step; never regress an
                       -- in-progress session's step back to "initial" on re-upsert.
```

**File:** `demetra/services/database.py:238-247`
```python
# before: vestigial COALESCE — EXCLUDED.step is always the literal "plan", never NULL,
# so the fallback to sessions.step was dead code
step = COALESCE(EXCLUDED.step, sessions.step),
# after
step = EXCLUDED.step,  -- Unlike upsert_pending_session, this call marks the plan step
                       -- as reached, so step always advances here.
```

## Test Results

- `uv run pytest -q` — **473 passed**.
- `uv run ruff check .` — clean.
- `uv run ty check` — clean (after adding the `row is not None` guard in Step 3).

---

## Source — [[2026-02-23-refactor-workflow-into-modular-steps]]

Originally added in [[2026-02-23-refactor-workflow-into-modular-steps]] on 2026-02-23
(MNT-37): the monolithic workflow in `main.py` was split into `demetra/workflows/*.py`
— a worktree-creation helper, an integrated plan agent, the lint/test runner from
MNT-21, and unified finalize actions (commit & push, PR creation, centralized cleanup
from MNT-19). Error handling is consolidated so every path terminates through the same
finalize/cleanup machinery. This is the basis of the current `demetra/workflows/`
layout.

## Source — [[2026-04-02-link-user-tasks-sessions]]

Originally added in [[2026-04-02-link-user-tasks-sessions]] on 2026-04-02 (MNT-63):
tasks and sessions are scoped to the logged-in user — every retrieved task and session
is linked to its user, and Linear task retrieval is filtered to projects linked to
that user. The separate `task_status` table was merged into `sessions` (status moved
onto the session; table and stale tests removed), and `sessions` gained `project_id`
and `user_id` columns with improved upserts. The `step`-based lifecycle this page
documents is the successor of that merged status concept.

## Follow-ups

- None.

> **Update (2026-08-18, Q-001 resolution):** `validate` was added to `StepType` in
> `demetra/library/models.py` (between `build` and `review`) to cover the
> validate-agent step set in `demetra/workflows/build.py:102`, which had previously
> been written without a matching enum value. `VALID_STEPS` in
> `demetra/api/sessions.py` now accepts `step=validate`. `awaiting_input` was added for PR/review failure paths (see [[2026-08-05-pr-creation-failure-handler]]); current `StepType` is `initial | plan | build | validate | review | lint | test | push | completed | failed | awaiting_input`.

> **Status update (2026-08-27, Consistency Agent):** `StepType` has since gained a 12th
> value: `"wiki"` (inserted between `test` and `push`), added in
> [[2026-08-25-mnt-187-wiki-pages-not-generated]] for the wiki-page-write session step.
> Current `StepType` is `initial | plan | build | validate | review | lint | test | wiki |
> push | completed | failed | awaiting_input`.

> **Status update (2026-09-01, Consistency Agent):** `StepType` has since gained a 13th
> value: `"research"` (inserted between `plan` and `build`), added in
> [[2026-09-01-mnt-177-research-loop]] for the research-agent step. Current `StepType` is
> `initial | plan | research | build | validate | review | lint | test | wiki | push |
> completed | failed | awaiting_input`.
>
> Also, `demetra/services/database.py` (cited in Steps 1–4 above) has moved to
> `demetra/services/persistence/database.py`; `demetra/api/sessions.py` is unchanged.
> Historical `file:line` refs above are kept as written.

## References

- Related: [[2026-07-16-simplify-session-logging-setup]] — the refactor this review was run against.
