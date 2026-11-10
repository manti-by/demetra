---
title: Durable review-round budget in sessions.review_attempts
date: 2026-11-10
type: implementation
status: resolved
session_id: ses_e3b031b40ffeslB7Om1aqmIcTt
services: [persistence, workflows, queue]
branch: opencode/feature/durable-review-attempts-budget
tickets: []
tags: [attempts, review-loop, durability, rq]
related: [2026-08-28-awaiting-input-workflow-continues-to-review.md, 2026-11-03-mnt-276-econnreset-retry-for-agents.md, 2026-10-12-session-state-flow-feedback-loops.md]
---

# Durable review-round budget in sessions.review_attempts

## TL;DR

The build step's review-round budget was a local variable, so every workflow
restart (watcher re-poll, `claim_session_for_resume`, re-enqueue) granted a
fresh `MAX_ATTEMPTS["review"]` rounds — a flappy session could loop
review → build indefinitely. The count of applied review rounds now lives in a
new durable `sessions.review_attempts` column (migration `e8f9a0b1c2d3`) and
the in-memory budget starts at `MAX_ATTEMPTS["review"] - stored`. Separately,
the RQ queue `default_timeout` was hardcoded 3600s and now derives from
`SUBPROCESS_TIMEOUT + 60` so a raised subprocess timeout can't get jobs killed
mid-run.

---

## Overview

- **Before:** `review_attempts = MAX_ATTEMPTS["review"]` was initialised at the
  top of `run_build_step` and decremented per applied round, entirely in
  memory. `run_attempts` and `listener_attempts` were already durable columns;
  review was the last counter that silently reset on every restart.
- **After:** `sessions.review_attempts` counts the rounds whose comments were
  applied as the next build task. The loop starts with the remaining budget
  (`MAX_ATTEMPTS["review"] - stored`), increments the column whenever a round's
  comments are applied, and resets it when the budget is deliberately renewed.
- Same PR: RQ queue timeout derived from `SUBPROCESS_TIMEOUT` instead of the
  hardcoded 3600.

**File:** demetra/workflows/build.py:111-117

```python
review_attempts = MAX_ATTEMPTS["review"] - (context.session.review_attempts if context.session else 0)
if review_attempts <= 0:
    review_attempts = 0
    print_message(
        f"Durable review budget exhausted ({MAX_ATTEMPTS['review']} rounds already applied).",
        style="warning",
    )
```

## Step 1 — Column and migration

**File:** demetra/library/tables.py:37, demetra/library/models.py:232,
migrations/versions/e8f9a0b1c2d3_add_sessions_review_attempts_column.py

- `sessions.review_attempts INTEGER NOT NULL DEFAULT 0` next to
  `run_attempts`/`listener_attempts`, with the same `server_default` pattern so
  the migration is a single `add_column` (no data backfill needed — every
  existing session starts with a fresh budget).
- `Session` dataclass gains `review_attempts: int = 0`.
- Every row → `Session` mapper now carries the field:
  `upsert_pending_session` (added to the `RETURNING` list), `get_session`,
  `get_session_by_pr_link` and `save_session`.

## Step 2 — Persistence helpers

**File:** demetra/services/persistence/database.py:366-430

- `increment_review_attempts(task_id)` — `SET review_attempts = review_attempts + 1 ... RETURNING review_attempts`; returns the new count (0 when the session is missing). Called when a round's comments are actually applied, so restarts resume the stored count.
- `reset_review_attempts(task_id)` — zeroes the column; called when a round's comments were deliberately skipped (manual mode) or a fresh lifecycle renews the budget.
- `reset_run_attempts` now also zeroes `review_attempts` in the same statement — moving an exhausted task back to `TODO` grants a fresh lifecycle, which includes a fresh review budget (matches the 2026-11-09 partial fix in [[2026-08-28-awaiting-input-workflow-continues-to-review]]).
- `claim_session_for_resume` clears `review_attempts` alongside `run_attempts`, `posted_to_linear` and the build plan when a chat session is re-run from `initial`.

## Step 3 — Build-loop wiring

**File:** demetra/workflows/build.py:191-225

- Auto mode: review comments returned → `review_attempts -= 1` **and**
  `await increment_review_attempts(task_id=...)` before `continue`.
- Manual mode: option `1` (apply) mirrors auto mode; option `2` (skip) resets
  the loop-local budget **and** `await reset_review_attempts(task_id=...)` —
  skipping a round is a deliberate renewal, not an applied round.
- The `awaiting_input` re-open path (confirmed re-open grants a new lifecycle)
  also calls `reset_review_attempts` next to the loop-local reset.
- When the durable budget is already exhausted, review is skipped entirely
  (`run_review_agents` never fires) with a warning, instead of restarting the
  budget at full strength.

## Step 4 — RQ queue timeout from SUBPROCESS_TIMEOUT

**File:** demetra/services/persistence/queue.py:9-10

```python
connection = Redis.from_url(url=REDIS_URL)
queue = Queue(connection=connection, default_timeout=SUBPROCESS_TIMEOUT + 60)  # Overhead for RQ itself
```

`SUBPROCESS_TIMEOUT` defaults to 1800s but is env-configurable; with the old
hardcoded `default_timeout=3600`, raising it past ~3540s would make RQ kill a
workflow job mid-run while the subprocess wrapper was still inside its legal
budget. The `+60` covers RQ's own bookkeeping overhead.

## Test Results

- `tests/test_database.py::TestReviewAttempts` — 4 new async tests: increment
  counts applied rounds (1 → 2), increment returns 0 for a missing session,
  reset renews the budget, and `reset_run_attempts` also clears
  `review_attempts`.
- `tests/test_workflows.py::TestWorkflowBuild` — 2 new tests:
  `test_run_build_step_skips_review_when_durable_budget_is_exhausted` (session
  with `review_attempts=5` → review agents never awaited, 1 build call) and
  `test_run_build_step_counts_applied_review_rounds_durably` (two build
  iterations, `increment_review_attempts` awaited once with the task id).
- `pytest` targeted run: 2 + 4 tests pass; `ruff check` and `ty check` clean on
  all touched files.

---

## Follow-ups

- None.

## References

- Related: [[2026-08-28-awaiting-input-workflow-continues-to-review]] — run-attempt reset on re-acceptance, whose statement now also renews the review budget
- Related: [[2026-11-03-mnt-276-econnreset-retry-for-agents]] — the other restart-resume path (agent network retries resume the opencode session; the review budget now survives the same kind of re-entry)
- Related: [[2026-10-12-session-state-flow-feedback-loops]] — the review → build feedback loop this budget bounds
