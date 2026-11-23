---
title: Test DB isolation and console-only logging
generated: {by: demetra, at: '2026-08-18T00:00:00Z'}
description: 'Records the fix for tests writing to the production demetra DB and demetra.log: making setup_test_db autouse and adding console_only_logging, plus persisting pending sessions and allowing websocket logs before a session row; outcome: 869 tests passed, though the page retains a contradictory Follow-ups section.'
type: debug
status: stable
session_id: '-'
services: [tests, database, settings, runtime, api, workflows, linear, main]
branch: feature/mnt-170-migrate-workflow-env-vars-to-projectuser-env-layers
tickets: [MNT-106]
tags: [tests, database, logging, isolation, test_demetra, conftest, websocket, sessions, console, ansi, fixtures]
related: [2026-06-15-remove-patches-from-tests.md, 2026-07-16-simplify-session-logging-setup.md, 2026-07-15-duplicated-log-messages.md, 2026-07-20-resolve-ansi-color-escape-codes-in-logs.md]
---

# Test DB isolation and console-only logging

## TL;DR

Tests wrote into the production `demetra` DB and spammed `/var/log/demetra/demetra.log` because `setup_test_db` wasn't autouse and `runtime/tui.py` installs a `FileHandler` at import. Fixed by making `setup_test_db` `autouse=True` (session-scoped) and adding `console_only_logging` that strips file handlers and patches `dictConfig`. Also fixed console runs leaving no session row and websocket logs being unreachable during the plan step.

---

## Symptom

- DB tests not requesting `setup_test_db` hit the live `demetra` DB instead of `test_demetra`.
- Suite appended to `/var/log/demetra/demetra.log` and created `sessions/{id}.log` files.

## Step 1 — DB isolation

**File:** `tests/conftest.py:100` — `setup_test_db` was `scope="session"` but not `autouse`; only callers got `DB_NAME = "test_demetra"`.

Affected (`tests/test_allowlist_cli.py:56` comment: "share the local development database"; `tests/test_allowlist.py:157+` UPDATEs roles; `tests/test_auth.py:330` JWT inserts). Fixture laziness meant any DB test before first `setup_test_db` request hit live DB.

## Step 2 — Log isolation

**File:** `demetra/services/runtime/tui.py:11` — `dictConfig(LOGGING)` at import (`settings.py:99` `file` handler at `LOG_PATH`) installs a `FileHandler` on root logger for the whole session. Plus `main.py:33`/`listener.py:19` re-run `dictConfig` inside tests, and `tests/test_workflows.py:1719` `test_main_calls_build_step_before_commit` didn't mock `setup_session_logging` → created real session files.

## Root cause

Opt-in isolation: DB redirect and console-vs-file distinction weren't guaranteed for the test process.

## Resolution

- `tests/conftest.py:114` — `setup_test_db` now `@pytest_asyncio.fixture(scope="session", autouse=True)`: fresh `test_demetra` (`drop/create + create_all`) and `DB_NAME = "test_demetra"`.
- `tests/conftest.py:67` — new autouse `console_only_logging`: strips `FileHandler`s from root logger and wraps `dictConfig` (via `patch.object` deepcopy) to drop the `file` handler from any lazy call.
- `tests/test_workflows.py:1725` — added `patch("main.setup_session_logging", AsyncMock)` to the affected test.

## Known follow-up

- Stale `demetra` DB artifacts from past runs not swept (currently none).
- `setup_test_db` autouse now requires Postgres for every `pytest` run (CI has one).

---

## Update — 2026-08-18 21:50 — console session persistence + websocket logs

**Step 1 — Console runs left no session row on early failure.** `make run-coruscant` only persisted session inside `run_plan_step` after plan agent; OpenRouter 429 in `extract_plan` aborted without a row (watcher path was fine — pending row before enqueue).

- `demetra/workflows/plan.py` — `extract_plan` wrapped `try/except PlanError` → error comment + `move_to_awaiting_input` (raises `AutoCancelledError`, cleanup rolls back worktree without reverting Linear status).
- `main.py` — at `main()` start: `if not context.session: await upsert_pending_session(...)` (guarded; `ON CONFLICT (task_id)` safe).
- `demetra/services/llm/openrouter.py` — `extract_plan` wraps LLM call, raises typed `PlanError`.

**Step 2 — No FE logs during plan step.** `/ws/v1/watcher/logs` required `get_session_id_by_task_id` (empty during `initial`/`plan` until opencode session persisted) → 4004.

- `demetra/api/watcher.py` — gate now `get_session_state(task_id, user_id)` (reject only if row belongs to another user); task with no session row still streams `sessions/{task_id}.log`. Status envelope adapts.

**Tests:** new in `tests/test_api.py` (websocket before-session), `tests/test_api_auth.py` (ownership reject), `tests/test_entrypoints.py` (pending session guards), `tests/test_openrouter.py`, `tests/test_workflows.py`. **869 passed**; `ruff`/`ty`/`bandit` clean.

---

## Source — [2026-06-15-remove-patches-from-tests](/archive/2026-06-15-remove-patches-from-tests.md)

Test-suite convention, originally decided on 2026-06-15 (MNT-106): replace `patch` DB mocks with real fixtures/factories and call local services directly — only third-party calls stay mocked — so refactors fail loudly instead of passing against a mock. The `setup_test_db` isolation on this page is what makes those real-DB tests safe.

## Source — [2026-07-15-duplicated-log-messages](/archive/2026-07-15-duplicated-log-messages.md)

The logging-dedup guard in `setup_session_logging()` must compare `Path` to `Path` (`Path(LOGGING["handlers"]["file"]["filename"]).resolve() == session_log_path.resolve()`) — the original `Path == str` comparison was always `False` and added a second `FileHandler` with `propagate=True`, duplicating every `print_message` line in session logs (fixed 2026-07-15). Same session: build-agent `stdout` is now logged on success (`print_message(f"Build agent output:\n{stdout.strip()}", ...)`) instead of being discarded, matching the plan-agent pattern. Originally recorded in [2026-07-15-duplicated-log-messages](/archive/2026-07-15-duplicated-log-messages.md).

## Source — [2026-07-16-simplify-session-logging-setup](/archive/2026-07-16-simplify-session-logging-setup.md)

`setup_session_logging(task_id)` (the unused `logger` param was dropped) has two cases, originally recorded on 2026-07-16: subprocess (`LOG_PATH=sessions/<task>.log`) — root already targets the session log, so reuse its `FileHandler` for `stream_logger` and return early (adding another handler duplicates output); in-process (merge/rebase, `LOG_PATH=demetra.log`) — build a new `FileHandler` and swap it onto root and `stream_logger`. A single `next(...)` lookup replaces the two handler loops. Originally recorded in [2026-07-16-simplify-session-logging-setup](/archive/2026-07-16-simplify-session-logging-setup.md).

## Source — [2026-07-20-resolve-ansi-color-escape-codes-in-logs](/archive/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md)

ANSI escapes are stripped from all log output (2026-07-20): `AnsiStrippingFilter` + `ansi_strip` (regex `\x1b\[[0-9;]*[a-zA-Z]`) applied at source in `live_stream`, registered in the `LOGGING` dictConfig on both `console` and `file` handlers, and attached to dynamically created session handlers in `setup_session_logging()`. Originally recorded in [2026-07-20-resolve-ansi-color-escape-codes-in-logs](/archive/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md).

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.
>
> **Consistency note (2026-11-03, Consistency Agent):** the watcher gate was renamed
> `get_session_step_name` → `get_session_state` in `1be4bfd` (MNT-244, 2026-10-12); the body now uses the
> current name (`demetra/services/persistence/database.py:1190`, `demetra/api/watcher.py:11`).

## References

- Related: [2026-06-15-remove-patches-from-tests](/archive/2026-06-15-remove-patches-from-tests.md), [2026-07-16-simplify-session-logging-setup](/archive/2026-07-16-simplify-session-logging-setup.md), [2026-07-15-duplicated-log-messages](/archive/2026-07-15-duplicated-log-messages.md)

> **Consistency note (2026-11-11, Consistency Agent):** This page has two follow-up sections that disagree: the “known follow-ups” list near the top (stale `demetra` DB artifacts; `setup_test_db` autouse now requires Postgres for every `pytest` run) and the `## Follow-ups` section at the bottom, which says “None”. The two listed items are the accurate ones; the bottom section should not read “None”.
