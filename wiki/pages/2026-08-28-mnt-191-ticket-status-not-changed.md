---
title: Ticket status isn't changed when watcher picks it up
date: 2026-08-28
type: implementation
status: resolved
session_id: "-"
services: [watcher, linear, daemons]
branch: "opencode/feature/mnt-191-ticket-status-not-changed"
tickets: [MNT-191]
tags: [watcher, linear, status, in-progress, todo, workflow, queue]
related:
- 2026-08-05-pr-creation-failure-handler.md
- 2026-07-21-rich-markuperror-and-run-attempts.md
- 2026-09-16-mnt-205-revise-merged-environment.md
---

# Ticket status isn't changed when watcher picks it up

## TL;DR

Watcher created a pending session and enqueued a workflow for TODO tickets but never moved the Linear ticket to `In Progress` itself — that update lived only in `main.py` after `setup_workflow` succeeded. On setup failure the ticket stayed in TODO and was re-picked every poll. `process_tasks` now moves the ticket to `in_progress` immediately on acceptance; `main.py` remains as safety net.

---

## Overview

Linear report: moving ticket to `Todo` did not change status to `In progress` after watcher pickup.

## Fix — `demetra/services/daemons/watcher.py:126-170` (`process_tasks`)

**Root cause:** `process_tasks` upserted pending session + enqueued RQ job but never touched Linear status. `main.py:98-103` updated to `in_progress` only inside `try` after `setup_workflow` succeeded; on `None` return (MNT-191 failure path) status never moved, ticket re-picked each poll until `MAX_RUN_ATTEMPTS`.

**Fix:** after upserting pending session in `if task.id not in pending_ids:`, resolve `in_progress` via `get_linear_config_value(name="in_progress", user_id=user_id)` and call `update_ticket_status`. Missing config → error log + continue; failed update → warning + continue; never crashes watcher loop.

```python
state_id = await get_linear_config_value(name="in_progress", user_id=user_id)
if state_id is None:
    logger.error(f"Linear state 'in_progress' is not configured for task {task.id}")
elif not await update_ticket_status(task_id=task.id, state_id=state_id):
    logger.warning(f"Failed to move task {task.id} to 'in_progress'")
```

Existing `main.py` update kept as safety net for manual CLI runs.

> **Status update (2026-09-01, Consistency Agent):** superseded by MNT-183 (`dfd64f6`, merged 2026-09-01): `in_progress` move lifted **outside** `if task.id not in pending_ids:` so every poll re-applies `in_progress` (idempotent) — handles tasks that revert to TODO while pending and transient `update_ticket_status` failures. Snippet above is the MNT-191 form kept as record.

## Tests — `tests/test_api_coverage.py` (`TestWatcherService`)

Fixtures: `mock_upsert_pending_session`, `mock_update_ticket_status`, `mock_get_linear_config_value`, `mock_delay_run_workflow`. Five tests:

- `test_process_tasks_moves_new_task_to_in_progress` — resolves with `task.user_id`, calls `update_ticket_status`, still enqueues.
- `test_process_tasks_skips_in_progress_update_for_existing_pending` — already pending → enqueue only.
- `test_process_tasks_logs_and_continues_when_in_progress_state_missing` — missing config logs error, still enqueues.
- `test_process_tasks_logs_and_continues_when_update_fails` — failed update logs warning, still enqueues.
- Two pre-existing tests refactored with `_task` helper.

## Test Results

- `uv run pytest tests/test_api_coverage.py -k TestWatcherService` — 6 passed
- `uv run pytest tests/` — 920 passed
- `uv run ruff check` / `uv run ty check` / `bandit` on `watcher.py` — clean

---

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-05-pr-creation-failure-handler]], [[2026-07-21-rich-markuperror-and-run-attempts]]
- External: Linear ticket MNT-191

> **Status update (2026-09-16, MNT-205):** `get_linear_config_value` was
> removed. `process_tasks` now resolves the state through the watcher's
> `_resolve_linear_state` helper, which builds a `SessionEnvironment` from the
> user-shared env and falls back to settings. See
> [[2026-09-16-mnt-205-revise-merged-environment]].
