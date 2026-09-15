---
title: Fix notification mark-as-read and add infinite-loop protection
date: 2026-07-16
type: implementation
status: resolved
session_id: ses_093670774ffeRqtTEflrkIDv8O
services: [listener]
branch: "-"
tickets: []
tags: [notifications, bug-fix, merge, rebase, listener-attempts, infinite-loop]
related: []
---

# Fix notification mark-as-read and add infinite-loop protection

## TL;DR

Two listener bugs fixed: (1) `process_merge/rebase_notification` returned `bool` success but `demetra/listener.py` discarded it and always called `mark_notification_read` — failed enqueues were lost. Now guarded by the return value. (2) No retry limit, so persistently failing notifications polled forever. Added `listener_attempts` (default 5, originally 3) mirroring `run_attempts` to break the loop after N failures.

> **Consistency note (2026-08-23):** handlers in `demetra/services/daemons/listener.py`; entrypoint is `demetra/listener.py`.

---

## Overview

- **Always marking read on failure**: notifications consumed even when no session, no `project_id`, or unknown action.
- **No infinite-loop protection**: permanent failures retried every cycle forever.

## Step 1 — Fix unconditional mark-as-read

**File:** `demetra/listener.py:50-64`

```python
processed = await process_merge_notification(...)
if processed:
    await mark_notification_read(...)
```

On `False` (no session / no `project_id` / unknown action), notification stays unread for retry.

## Step 2 — Add listener attempts counter

- **Schema** (`demetra/library/tables.py`, `models.py`): `listener_attempts` on `sessions` (not null, default 0, after `run_attempts`). Migration `b3c4d5e6f7a8_add_sessions_listener_attempts_column`.
- **Settings**: `MAX_LISTENER_ATTEMPTS` (3 → later `int(os.environ.get(..., 5))`).
- **DB** (`demetra/services/database.py`): `increment_listener_attempts`/`reset_listener_attempts`, updated `INSERT`s and `Session` constructions.
- **Listener** (`demetra/services/daemons/listener.py`): increments on entry; if > max returns `True` (marks read to break loop); on success resets to 0; on `no project_id`/unknown returns `False`.

## Test Results

489 tests pass. New tests: `tests/test_listener.py` (4: mark-read gating for merge/rebase + max-attempts) and `tests/test_database.py` `TestListenerAttempts` (start 0, increment, reset, re-upsert preservation, 0 for missing rows).

---

## Follow-ups

None.

## References

- Related: none
