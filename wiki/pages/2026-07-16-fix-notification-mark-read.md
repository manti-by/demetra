---
title: Fix notification mark-as-read and add infinite-loop protection
date: 2026-07-16
type: implementation
status: resolved
session_id: ses_093670774ffeRqtTEflrkIDv8O
services: [listener]
branch: -
tickets: []
tags: [notifications, bug-fix, merge, rebase, listener-attempts, infinite-loop]
related: [2026-07-15-duplicated-log-messages.md]
---

# Fix notification mark-as-read and add infinite-loop protection

## TL;DR

Two bugs in `listener.py`: (1) `process_merge_notification`/`process_rebase_notification` returned a `bool` indicating success, but `listener.py` discarded it and called `mark_notification_read` unconditionally, so failed enqueues were lost forever. (2) Without a retry counter, a persistently failing notification would poll indefinitely every cycle. Fixed by guarding `mark_notification_read` with the return value, and adding a `listener_attempts` column (with `MAX_LISTENER_ATTEMPTS=3`) that breaks the loop after 3 failures, mirroring the `run_attempts` pattern.

---

## Overview

Two distinct failure modes were fixed in the notification listener:

1. **Always marking notifications as read on failure** — `process_merge_notification`/`process_rebase_notification` (in `demetra/services/listener.py`) returned a `bool` indicating whether the workflow was successfully enqueued, but `listener.py` discarded that return value and invoked `mark_notification_read` unconditionally. This meant notifications were consumed even when:
   - No session existed for the PR link
   - The session had no `project_id`
   - The action was unknown

2. **No infinite-loop protection** — Notifications that persistently failed (e.g. a session that never gets a `project_id`) would be polled every cycle forever with no backoff or circuit-breaker. Added a `listener_attempts` counter on the `sessions` table that trips a `MAX_LISTENER_ATTEMPTS=3` threshold and forces the notification as read, mirroring the existing `run_attempts` pattern for workflow re-enqueue loops.

## Step 1 — Fix unconditional mark-as-read

**File:** `demetra/listener.py:50-64`

The main loop called `process_merge_notification`/`process_rebase_notification` but discarded the `bool` return value and called `mark_notification_read` on every match:

```python
if merge_match:
    processed = await process_merge_notification(...)
    ...
    if processed:
        await mark_notification_read(...)
```

On failure (`processed` is `False`), a warning is logged and the notification stays unread so it is retried on the next poll cycle.

Processing returns `False` when:
- No session exists for the PR link
- The session has no `project_id`
- The action (merge/rebase) is unknown

## Step 2 — Add listener attempts counter

**Schema & migration:**
- `demetra/library/tables.py` — added `listener_attempts` column to `sessions` table (not null, default 0), positioned after `run_attempts`
- `demetra/library/models.py` — added `listener_attempts: int = 0` to `Session` dataclass
- `demetra/settings.py` — added `MAX_LISTENER_ATTEMPTS = 3`
- `migrations/versions/b3c4d5e6f7a8_add_sessions_listener_attempts_column.py` — new Alembic migration (head `b3c4d5e6f7a8`)

**Database layer:**
- `demetra/services/database.py` — added `increment_listener_attempts(task_id)` returning the new count, and `reset_listener_attempts(task_id)` to zero it on success. Updated both `INSERT` statements and all 5 `Session(...)` constructions.

**Listener logic** (`demetra/services/listener.py` `process_notification`):
- Fetches session; returns `False` (leaves notification unread) when no session exists
- Increments `listener_attempts` on entry
- If counter exceeds `MAX_LISTENER_ATTEMPTS`, logs a warning and returns `True` so the caller marks the notification as read (breaking the loop)
- On successful enqueue, resets the counter to 0 (transient failures won't permanently exhaust retries)
- On `no project_id` / unknown action, returns `False` (left unread for retry; counter increments each time)

## Test Results

All 489 tests pass. New tests added:
- `tests/test_listener.py`: 4 tests — mark-read gating on success/failure for both merge and rebase, plus max-attempts-exceeded behavior for both
- `tests/test_database.py`: `TestListenerAttempts` class — covers start at 0, increment sequence, reset, preservation on re-upsert, and 0 for nonexistent rows

---

## Follow-ups

- None

## References

- Related: [[2026-07-15-duplicated-log-messages]] — prior listener bug (duplicate log writes)
