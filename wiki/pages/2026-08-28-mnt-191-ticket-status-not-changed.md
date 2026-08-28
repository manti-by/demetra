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
related: [2026-08-05-pr-creation-failure-handler.md, 2026-07-21-rich-markuperror-and-run-attempts.md]
---

# Ticket status isn't changed when watcher picks it up

## TL;DR

When the watcher daemon picked up a TODO task it created a pending session and enqueued a
workflow, but never moved the ticket to `In Progress` itself — it relied on `main.py`
updating the status only after `setup_workflow` succeeded. If setup failed the ticket stayed
stuck in TODO forever and was re-picked every poll. `process_tasks` now moves a new task to
`in_progress` the moment it accepts it. Tests added.

---

## Overview

The Linear ticket reported: "When ticket moved in `Todo` and watcher picked it up status
isn't changed from `Todo` to `In progress`".

## Step 1 — Move a task to `in_progress` when the watcher accepts it

**File:** `demetra/services/daemons/watcher.py:126-170` (`process_tasks`)

Root cause: `process_tasks` picked up TODO tasks, upserted a pending session row and enqueued
a workflow run on the RQ queue, but never touched the Linear status. The `in_progress`
update lived only in `main.py:98-103`, inside the `try` block **after** `setup_workflow` had
already succeeded. If `setup_workflow` failed it returned `None` from `main.py:74` and the
ticket was never moved out of TODO. On the next poll the same task was picked again, a
duplicate pending session was created and another workflow enqueued, leaving the ticket stuck
in TODO until `MAX_RUN_ATTEMPTS` was hit.

Fix: inside the `if task.id not in pending_ids:` block, right after the pending session is
upserted, resolve the `in_progress` state via `get_linear_config_value` (reusing the same
`user_id`) and call `update_ticket_status`. A missing config logs an error and continues; a
failed update logs a warning and continues — the watcher loop is never crashed.

```python
if task.id not in pending_ids:
    user_id = task.user_id or DEFAULT_USER_ID
    if not task.project_id or not user_id:
        logger.warning(f"Skipping task {task.id}: missing project_id={task.project_id}, user_id={user_id}")
        continue
    await upsert_pending_session(
        task_id=task.id,
        session_id=None,
        project_id=task.project_id,
        user_id=user_id,
        name=task.full_title,
        linear_link=task.url,
    )

    state_id = await get_linear_config_value(name="in_progress", user_id=user_id)
    if state_id is None:
        logger.error(f"Linear state 'in_progress' is not configured for task {task.id}")
    elif not await update_ticket_status(task_id=task.id, state_id=state_id):
        logger.warning(f"Failed to move task {task.id} to 'in_progress'")
```

The existing `in_progress` update in `main.py` remains as a safety net for manual CLI runs.

## Step 2 — Tests

**File:** `tests/test_api_coverage.py` (`TestWatcherService`)

Added fixtures (`mock_upsert_pending_session`, `mock_update_ticket_status`,
`mock_get_linear_config_value`, `mock_delay_run_workflow`) and five new tests:

- `test_process_tasks_moves_new_task_to_in_progress` — asserts the state is resolved with the
  task's `user_id`, `update_ticket_status` is called with the resolved id, and the workflow is
  still enqueued.
- `test_process_tasks_skips_in_progress_update_for_existing_pending` — a task already pending
  is enqueued without touching the status.
- `test_process_tasks_logs_and_continues_when_in_progress_state_missing` — a missing config
  logs an error but the workflow is still enqueued.
- `test_process_tasks_logs_and_continues_when_update_fails` — a failed status update logs a
  warning but the workflow is still enqueued.
- The two pre-existing tests (`filters_missing_project_name`, `skips_missing_project_id`) were
  refactored to share a `_task` helper.

## Test Results

- `uv run pytest tests/test_api_coverage.py -k TestWatcherService` — 6 passed.
- `uv run pytest tests/` — 920 passed.
- `uv run ruff check demetra/services/daemons/watcher.py tests/test_api_coverage.py` — clean.
- `uv run ty check demetra/services/daemons/watcher.py` — clean.
- `uv run bandit -c pyproject.toml demetra/services/daemons/watcher.py` — 0 issues.

---

## Follow-ups

None.

## References

- Related: [[2026-08-05-pr-creation-failure-handler]], [[2026-07-21-rich-markuperror-and-run-attempts]]
- External: Linear ticket MNT-191
