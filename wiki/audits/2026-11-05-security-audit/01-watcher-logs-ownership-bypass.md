# 01 — Watcher log WebSocket streams a foreign session's logs

## Summary

- **Title:** Log WebSocket keeps streaming after a task becomes owned by another user
- **Problem:** `watcher_logs` authenticates the subscriber, but treats an *absent*
  session row as permission to stream a task's log without ever recording task
  ownership. If a victim's session is created *after* an attacker subscribes, the
  connect-time check passes (no session exists yet) and the polling loop never
  re-checks ownership, so the attacker keeps receiving the victim's newly written
  log lines.
- **Date:** 2026-11-05
- **Severity:** low · **CWE-863** · **Category:** authorization_bypass
- **CodeRabbit ID:** `ed8d33cf-b34d-4caf-8275-cf9975cd7d04`
- **Files (current):** `demetra/api/watcher.py:104-108` (connect-time check),
  `demetra/api/watcher.py:147-212` (stream loop)
- **Revalidation:** Confirmed. The connect-time guard only rejects when a session row
  *already* exists and belongs to another user; the pre-session subscription path
  (`seen_session = False`) continues streaming without an ownership re-check.

## Steps

1. Track ownership explicitly instead of inferring it from "no row". Introduce a
   subscription flag (e.g. `owned = status_info is not None`) set at connect time.
2. Reject pre-session subscriptions that carry no ownership record, or authorise them
   only against the task's owning project. At minimum, require that the session row
   exist and belong to `user.id` before `await websocket.accept()` at
   `demetra/api/watcher.py:127`.
3. In the polling loop (`demetra/api/watcher.py:184-212`), re-check ownership every
   tick: if `get_session_state(task_id=task_id, user_id=user.id)` is `None` while
   `get_session_state(task_id=task_id)` is not `None` (session now owned by someone
   else), send `reject_connection(..., code=4004)` / close the socket and break.
4. Apply the same re-check before the log-file reads at lines 149-182 so newly written
   foreign log content is never streamed.
5. Add a regression test (`tests/`) covering: subscribe with no session → a session is
   created for another user → the socket is closed and no further lines are delivered.
