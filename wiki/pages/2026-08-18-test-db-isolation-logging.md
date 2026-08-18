---
title: Test DB isolation and console-only logging
date: 2026-08-18
type: debug
status: resolved
session_id: -
services: [tests, database, settings, runtime, api, workflows, linear]
branch: feature/mnt-170-migrate-workflow-env-vars-to-projectuser-env-layers
tickets: []
tags: [tests, database, logging, isolation, test_demetra, conftest, websocket, sessions, console]
related: [2026-06-15-remove-patches-from-tests.md, 2026-07-16-simplify-session-logging-setup.md, 2026-07-15-duplicated-log-messages.md]
---

# Test DB isolation and console-only logging

## TL;DR

The test suite was writing into the real `demetra` database and the production
log files: `setup_test_db` (which swaps `DB_NAME` to `test_demetra`) was not
autouse, so DB-touching tests that never requested it (allowlist CLI/auth)
hit the live database, and `demetra/services/runtime/tui.py` installs a
`FileHandler` on the root logger at import time, so every test's `print_message`
output landed in `/var/log/demetra/demetra.log` (plus per-session files from one
`main()` test). Fixed by making `setup_test_db` autouse and adding a
`console_only_logging` fixture that strips file handlers and wraps `dictConfig`
to drop the `file` handler. Verified: 867 tests pass, `test_demetra` receives all
test rows, the main DB stays clean, and no session/app log files are touched.

---

## Symptom

- DB-touching tests that do not request `db_connection`/`setup_test_db` run
  against the production `demetra` database instead of `test_demetra`.
- Running the suite appends test log output to `/var/log/demetra/demetra.log`
  and creates per-task files under `/var/log/demetra/sessions/`.

## Step 1 — Tests wrote into the production `demetra` database

**File:** tests/conftest.py:100 — `setup_test_db` was `scope="session"` but **not**
`autouse`. It only ran for tests that explicitly requested `db_connection` or
`setup_test_db`, and only then did it set `_database_module.DB_NAME = "test_demetra"`.

Tests that call `get_connection()`/`create_user()` directly without requesting the
fixture silently fell through to the default `DB_NAME` (`demetra`):

- **File:** tests/test_allowlist_cli.py:56 — the `clean_allowlist` autouse
  fixture even documented it: "The CLI tests share the local development database
  with the rest of the suite" and `DELETE FROM allowlist_entries` on the live DB.
- **File:** tests/test_allowlist.py:157,171,188,206 — `_database_module.get_connection()`
  UPDATEs user roles on the live DB.
- **File:** tests/test_auth.py:330 — `get_connection()` inserts JWT rows on the live DB.

Because session-scoped fixtures are lazy, any DB test running before the first
`setup_test_db` request (e.g. `test_allowlist_cli` sorts first) hit the live DB.

## Step 2 — Tests spammed the app log and created session files

**File:** demetra/services/runtime/tui.py:11 — `logging.config.dictConfig(LOGGING)`
runs at import time. `LOGGING` (demetra/settings.py:99) has a `file` handler at
`LOG_PATH` (`/var/log/demetra/demetra.log`). tui is imported during collection
(via `demetra.app` → services), so a `FileHandler` sat on the root logger for the
whole session and every `logger.info` (incl. `print_message`) was written to the
production log.

Two additional vectors:

- `main.py:33`, `demetra/listener.py:19` re-run `dictConfig` on lazy import
  *inside* tests (`tests/test_entrypoints.py`, `tests/test_listener.py`), re-adding
  the file handler mid-session.
- **File:** tests/test_workflows.py:1719 `test_main_calls_build_step_before_commit`
  runs `main()` but did **not** mock `main.setup_session_logging`, so the real
  function created `sessions/{uuid}.log` files for the fake task ids.

## Root cause

Test isolation was opt-in rather than guaranteed:

- DB redirect only applied after a fixture that not every DB consumer requested.
- The console-only vs file logging distinction was never handled for the test
  process; tui's import-time `dictConfig` configures the process-global root logger
  with production handlers.

## Resolution / Fix

- **File:** tests/conftest.py:114 — `setup_test_db` is now
  `@pytest_asyncio.fixture(scope="session", autouse=True)`: the whole session
  starts with a fresh `test_demetra` (drop/create + `metadata.create_all`) and
  `DB_NAME = "test_demetra"`.
- **File:** tests/conftest.py:67 — new autouse `console_only_logging` fixture:
  - strips any `FileHandler` from the root logger, and
  - wraps `logging.config.dictConfig` (via `patch.object`) to deepcopy the config,
    remove the `file` handler and drop `file` from every logger's handler list, so
    any lazy `dictConfig` call during tests stays console-only.
- **File:** tests/test_workflows.py:1725 — added
  `patch("main.setup_session_logging", new_callable=AsyncMock)` to the
  `test_main_calls_build_step_before_commit` patch block.

## Known follow-up (not fixed this session)

- The stale test artifacts already written into the live `demetra` DB by past runs
  (users/allowlist rows) were not swept; the main DB currently has none, but a one-off
  cleanup is worth confirming if any `@example.com` test users remain.
- The session-scoped autouse `setup_test_db` now requires a reachable Postgres for
  *every* pytest run (previously only DB tests did); CI already provides one.

---

## Update — 2026-08-18 21:50

### Console-run session persistence and websocket log retrieval

Follow-up on this session's logging/console-run theme: two related fixes so a
console `main.py --no-auto` run is visible on the FE from the very first step.

**Step 1 — Console runs left no session row when a run died early.**
`make run-coruscant` (console path) only persisted a session inside
`run_plan_step` via `save_session`, *after* the plan agent produced a plan. When
plan summarization failed (OpenRouter 429) `extract_plan` raised an uncaught
error, the run aborted, and no DB row was ever written. The watcher path was
fine because it upserts a pending row before enqueuing. Fixes:
- **File:** demetra/workflows/plan.py — `extract_plan` wrapped in
  `try/except PlanError`: posts an error comment, then `move_to_awaiting_input`
  (moves ticket to Awaiting Input + session step + raises `AutoCancelledError`
  so cleanup rolls back the worktree without reverting the Linear status).
- **File:** main.py — at the start of `main()`, `if not context.session:
  await upsert_pending_session(...)` so every run leaves a DB row. Guarded by
  the existing-session check, so watcher/worker runs (which already create the
  pending row) never duplicate it; `ON CONFLICT (task_id)` makes it safe anyway.
- **File:** demetra/services/llm/openrouter.py — `extract_plan` now wraps its
  LLM call and raises typed `PlanError` instead of leaking a rate-limit error.

**Step 2 — No logs on FE during the plan step.**
The `/ws/v1/watcher/logs` gate used `get_session_id_by_task_id`, which returns
`None` while the session row has an empty `session_id` (the state during
`initial`/`plan`, since the opencode session id is only persisted after the plan
agent finishes) — so the FE connection was rejected with 4004 before streaming.
Fix: the endpoint now keys log retrieval purely by `task_id` (the file has
always been `sessions/{task_id}.log`) and no longer requires a session row to
connect.
- **File:** demetra/api/watcher.py — gate changed to
  `get_session_step_name(task_id, user_id)` for the soft ownership check
  (reject only if a session row exists for another user); a task with no
  session row yet still streams its log file. Status streaming adapts: no
  `status` envelope until a session appears, and `deleted`/close only when a
  previously-seen session disappears.

**Test results** — new tests in tests/test_api.py
(`test_websocket_streams_logs_before_session_row_exists`,
`test_websocket_streams_logs_for_pending_session_without_session_id`),
tests/test_api_auth.py (`test_websocket_rejects_task_owned_by_another_user`),
tests/test_entrypoints.py (`test_main_creates_pending_session_when_session_missing`,
`test_main_skips_pending_session_when_session_exists`),
tests/test_openrouter.py, tests/test_workflows.py. Full suite: **869 passed**;
`ruff`, `ty`, `bandit` clean.

---

## Follow-ups

- None.

## References

- Related: [[2026-06-15-remove-patches-from-tests]], [[2026-07-16-simplify-session-logging-setup]], [[2026-07-15-duplicated-log-messages]]
- External: none