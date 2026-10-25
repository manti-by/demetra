---
title: Session history — session cost total and failure reasons
date: 2026-10-25
type: implementation
status: resolved
session_id: ses_e8cb0a5a3fferHYaEAjpMs6ONG
services: [main, api, library, persistence, workflows, migrations, react, tests]
branch: "-"
tickets: []
tags: [session-history, token-accounting, frontend, cost, failure-reasons]
related: [2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-mnt-245-empty-session-history.md, 2026-08-05-pr-creation-failure-handler.md]
---

# Session history — session cost total and failure reasons

## TL;DR

Two UI-facing gaps in the session-history timeline: (1) the modal showed per-step
cost but no session-wide total — the API's `_compute_total_tokens` summed token
counters only; (2) `failed`/`awaiting_input` step cards gave no hint of why, since
failure details went to Linear comments and logs, never to the history row. Fixed
by summing `row.cost` into `total["cost"]` and rendering a "Total Cost" cell, and
by adding a nullable `session_history.message` column that carries the failure
reason — threaded from `main.py`'s exception handlers through `cleanup_workflow`
into `record_session_step` — rendered as a neutral (not red) callout block on the
card. 1025 backend + 109 frontend tests pass; `ruff`/`ty`/`tsc` clean.

---

## Overview

Two independent fixes landed in the same session, both touching the history
pipeline end to end: persistence (`record_session_step`, `get_session_history`),
serialization (`demetra/api/sessions.py`), and the React `SessionHistory`
component plus its global CSS and test fixtures.

## Step 1 — Session-wide cost total

**File:** `demetra/api/sessions.py` — `_compute_total_tokens`

The `total` dict aggregated five token counter fields across `kind='invocation'`
rows but skipped `cost` entirely, even though `_serialize_history_row` exposed it
per row and the card rendered it. The totals block (`TotalTokensBlock` in
`react/src/components/SessionHistory.tsx`) therefore had nothing to show.

- Added `"cost": 0.0` to the initial dict and `total["cost"] += row.cost or 0.0`
  inside the invocation-row loop (before: simply absent — no other writer needed
  touching, the cursor model already persists exact per-invocation deltas).
- `react/src/services/api.ts` — `SessionTokenTotals` and `EMPTY_TOKEN_TOTALS`
  gained `cost: number`; the duplicate empty-constant in `SessionArtifacts.tsx`
  was widened to match the type.
- `SessionHistory.tsx` renders a `Total Cost` cell (`$X.XXXX`) in the
  `session-history-totals-grand` style, next to the token grand total.

**Note:** the test-fixture drill mattered — `SessionHistoryEntry.cost` mocks had
to be set in `SessionHistory.test.tsx`, `SessionArtifacts.test.tsx` and the
StyleGuide before `tsc` recognized the widened `SessionTokenTotals`.

## Step 2 — Failure reason persisted on the step row

**Files:** `demetra/library/tables.py`, `demetra/library/models.py`,
`migrations/versions/e0f1a2b3c4d5_add_session_history_message_column.py`

- New nullable `message` column (`Text`) on `session_history`; migration chains
  on top of `d9e0f1a2b3c4`. `SessionHistory` dataclass gains `message: str | None`.
- `record_session_step` in `demetra/services/persistence/database.py:763` accepts
  `message: str | None = None`. Upsert semantics per `(task_id, step)`:
  new rows store the message; on an existing row a provided message overwrites
  and `None` preserves it. This ordering lets an inner path record a reason that
  the later cleanup call (which passes `None`) will not erase.
- `get_session_history` reads the column back; `_serialize_history_row`
  (`demetra/api/sessions.py`) exposes it as `"message"`.

## Step 3 — Threading the reason from the failure sites

**Files:** `main.py`, `demetra/workflows/cleanup.py`, `demetra/workflows/plan.py`

- `cleanup_workflow` gained `failure_message: str | None = None` and forwards it
  to `record_session_step` for the failure-step row it records.
- `main.py` keeps `failure_message: str | None = None` and every `except`
  handler captures `failure_message = str(e) or None` (the `or None` normalizes
  bare raises like `AutoCancelledError` in `plan.py`, which stringify to `""`).
  Handlers for PullRequest/Review/Wiki/Build errors, `DemetraError`,
  `ValueError`, `OSError`, `RuntimeError` and the cancellation classes are all
  wired.
- `awaiting_input` context: `move_to_awaiting_input(context, reason)` in
  `plan.py` now raises `AutoCancelledError(reason)` instead of a bare raise,
  with two reasons — `"Plan step failed: {e}"` after a failed plan extraction
  and `"Plan questions posted to Linear, waiting for answers"` when questions
  are posted. The exception reaches `main.py`, whose handler already threads
  messages, so the awaiting-input row carries the same context.

## Step 4 — Failure-reason rendering

**Files:** `react/src/components/SessionHistory.tsx`, `react/src/App.css`

- A card renders `<p class="session-history-failure" title="Failure reason">`
  whenever `entry.message != null` — covers both `failed` and `awaiting_input`
  step cards (those rows carry no tokens, so previously only the header showed).
- Styling deliberately NOT red per user instruction: regular secondary text
  color, `var(--color-border)` / `var(--color-surface-3)` neutral background,
  mono font, `white-space: pre-wrap` + `overflow-wrap: anywhere` for exception
  strings.

## Test Results

- Backend: `tests/test_database.py` (upsert/overwrite/preserve message),
  `tests/test_api.py` (total includes `cost`; `"message"` round-trips), 
  `tests/test_workflows.py` (cleanup asserts `record_session_step` called with
  the message), `tests/test_entrypoints.py` (all delegated-failure tests assert
  the exact `failure_message` passed to cleanup) — 1025 passed total.
- Frontend: card renders the failure block (`/\.session-history-failure/`) and
  omits it without a message — 109 passed; `tsc --noEmit` clean.
- Lint: `ruff check` on `demetra`/`tests`/`main.py`/`migrations`, `ty check`,
  `bandit` untouched areas — all clean.

---

## Follow-ups

- Failure paths that record via Linear comments but exit without a raised
  error (e.g. `run_plan_step` returning `None` on an empty plan, research early
  returns) still leave the terminal `failed` row message-less — could thread a
  reason string there too.
- `record_agent_invocation` rows never carry `message`; if an invocation-level
  failure reason is ever wanted it would need the same column treatment on the
  write path.
- No `raycast`-style changelog entry was needed; migration `e0f1a2b3c4d5` is a
  additive nullable column so backfill is a no-op.

## References

- Related: [[2026-10-16-mnt-251-session-attribution-accounting]] — introduced the
  `kind='step'`/`'invocation'` split and the `(task_id, step)` upsert the message
  threads into.
- Related: [[2026-10-16-mnt-245-empty-session-history]] — the empty-card symptom
  that motivated terminal failure rows carrying more than a header.
- Related: [[2026-08-05-pr-creation-failure-handler]] — the Linear-comment
  failure path whose reasons now also land in history rows.
- External: no Linear ticket (user-reported inline).
