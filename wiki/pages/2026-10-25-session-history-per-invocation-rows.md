---
title: Session history — one row per agent invocation
date: 2026-10-25
type: debug
status: resolved
session_id:
services: [persistence, api, react, workflows]
branch: opencode/feature/session-history-per-invocation-rows
tickets: []
tags: [session-history, agent-sessions, tokens, tool-usage, build-loop, validate]
related: [2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-25-mnt-258-tool-usage-stats.md, 2026-10-16-mnt-234-isolate-session-context.md, 2026-10-16-mnt-245-empty-session-history.md, 2026-10-25-session-history-cost-and-failure-reasons.md]
---

# Session history — one row per agent invocation

## TL;DR

The session-history modal showed `build → validate → validate → validate → review` even though the workflow
ran exactly one validate per build. `record_agent_invocation` upserted `kind='invocation'` rows per
`(task_id, session_id, step)` and accumulated the delta, so **every resumed build iteration collapsed into the
row created by the first one**, while validate/review (a fresh opencode session per round) got a row each.
Invocations now always insert their own history row, and tool counts are keyed by `(history_id, tool_name)`
(migration `f2a3b4c5d6e7`).

---

## Symptom

Requested check: the latest session (`df5bff3a-e9ed-45e0-a3ee-0274de2f8edf`, odin / MNT-255) shows 2–3
`validate` cards in a row after a single `build` card, while the expected order is `build → validate → build`
or `build → validate → review`.

**Evidence — the log is a perfect alternation** (`/var/log/demetra/sessions/df5bff3a-….log`):

```
18:31:33 BUILD  → 18:44:52 VALIDATE → review
18:54:17 BUILD  → 19:00:05 VALIDATE
19:00:49 BUILD  → 19:01:23 VALIDATE
19:01:55 BUILD  → 19:03:57 VALIDATE → review
19:09:46 BUILD  → 19:15:34 VALIDATE → review
19:21:33 BUILD  → 19:21:47 VALIDATE
19:23:29 BUILD  → 19:23:54 VALIDATE → review
19:30:09 BUILD  → 19:39:47 VALIDATE → review
```

`Running BUILD agent` ×8, `Running VALIDATE agent` ×8 — one validate per build, as designed.

**But `session_history` returned only one `build` row:**

```
plan, build(18:44:52), validate(18:45), review×3,
validate(19:00:49), validate(19:01:55), validate(19:04:36), review×3,
validate(19:16), review×3, validate(19:23), validate(19:24), failed,
build(19:39), validate, review×3, completed
```

Build iterations 2–7 are missing; the timeline reads as consecutive validates.

## Root cause

Three facts compound:

1. **Only the first build forks.** `demetra/workflows/build.py:109` — `fork = is_first_build and
   context.session_id is not None`; later iterations resume the same opencode session.
2. **Validate always starts a new session.** `demetra/workflows/validate.py:49` passes no `session_id`, so
   every round is a distinct opencode session.
3. **The writer collapsed per-session iterations.** `record_agent_invocation` selected the existing
   `session_history` row by `(task_id, session_id, step, kind='invocation')` and accumulated the delta onto it
   — the MNT-251 design ("build iterations share one `(session, step)` row"), which was right for token totals
   and wrong for the timeline.

`get_session_history` orders by `created_at` (`demetra/services/persistence/database.py`) and
`SessionHistoryCard` renders one card per row, so the single build row kept the timestamp of the first
iteration (18:44:52) and every later build vanished between validate cards.

Ruled out:

- Duplicate validate invocations — the log shows exactly 8 validate runs for 8 builds.
- A validate retry inside `run_validate_agent` — one `opencode run` per call.
- Session mis-attribution — every validate row carries `agent=validate-agent` and a distinct `ses_…` id.
- The second `run_build_step` in `main.py:156` (commit retry) — it re-forks (a new session id, visible in the
  history as the second `build` row) and only runs when `commit_and_push` fails, not per iteration.

## Resolution / Fix

**File:** `demetra/services/persistence/database.py` — `record_agent_invocation` now always inserts a fresh
`session_history` row; the delta `max(0, cumulative − cursor)` is already the exact per-invocation increment,
so nothing needs accumulating. `agent_sessions` stays the cursor (one row per `(task_id, session_id)`).

**File:** `demetra/library/tables.py` — `session_tool_usage` gains `history_id` (FK → `session_history.id`,
`ON DELETE CASCADE`) with `UniqueConstraint("history_id", "tool_name")`, replacing
`uq_session_tool_usage_row (agent_session_id, step, tool_name)`. Without this, N rows sharing
`(agent_session_id, step)` would each be handed the same aggregated tool list by `get_session_history` and
`_compute_tool_usage` would double count.

**File:** `migrations/versions/f2a3b4c5d6e7_alter_session_tool_usage_add_history_id.py` — adds and backfills
`history_id` from the previous `(agent_session_id, step)` pairing, swaps the unique constraint; the downgrade
merges duplicate tool rows (sum of counters, earliest id) before restoring the old constraint.

**File:** `demetra/services/persistence/database.py` — `get_session_history` attaches tool usage by
`history_id` instead of `(agent_session_id, step)`.

Token totals are unchanged: summing the per-invocation deltas equals the previous accumulated row
(`_compute_total_tokens` in `demetra/api/sessions.py` already sums only `kind='invocation'` rows). No frontend
change was needed — the timeline simply receives the real sequence now.

## Test Results

Updated `tests/test_database.py` to the per-invocation contract (deltas instead of accumulated totals, tool
rows per history row, list-based `_fetch_tool_usage` helper) and added the regression that reproduces the bug:

```python
history = await get_session_history(task_id=task_id)
assert [(row.step, row.input_tokens) for row in history] == [
    ("build", 1000), ("validate", 100), ("build", 500),
]
```

- `uv run pytest tests/` — 1054 passed, 1 pre-existing environment failure
  (`tests/test_settings.py::TestSettings::test_opencode_defaults` asserts the opencode binary lives under
  `.opencode`, but this host resolves `/usr/local/bin/opencode`).
- Migration verified on a scratch Postgres database: upgrade backfills `history_id`, downgrade merges
  duplicate tool counters (2 rows `3 + 4` calls → one row with 7), then both are dropped.
- `ruff check`, `ruff format --check`, `ty check`, `bandit` clean.

---

## Follow-up — non-agent step rows (lint, test, wiki, push)

Second report on the same session: `lint` / `test` cards missing from the timeline. The frontend and API were
fine — the rows were never written.

**Root cause:** `update_session_step` stopped writing history in MNT-251, but only `cleanup.py`'s
`completed` / failure paths were migrated to `record_session_step`. `run_lint_and_test`
(`demetra/workflows/lint.py:41,58`) still called `update_session_step` alone, so `lint` / `test` advanced
`sessions.step` (visible in the live flow bar) but never reached `session_history`; `wiki` / `push` in
`commit_and_push` (`demetra/workflows/cleanup.py:47,68`) had the same gap. Evidence: `session_history` has
`lint` / `wiki` / `push` step rows only up to 2026-10-12 (before `82ad9d0`); no `test` row was ever written.

**Fix:** `run_lint_and_test` records `lint` / `test` when the tool actually starts (not on the final step
reset, so a disabled feature cannot create a phantom row); `commit_and_push` records `wiki` and `push`. Tests
assert the recorded step sequence and that disabled features record nothing.

Note: this deployment has `IS_RUFF_ENABLED` / `IS_PYTEST_ENABLED` unset, so lint/tests are skipped entirely —
enabling them is required for those rows to appear in the latest sessions.

## Follow-ups

- Legacy rows written before this change keep their accumulated build row (nothing to split retroactively).
- `session_history.message` for `kind='invocation'` is still unused; failures are recorded on step rows.

## References

- Related: [[2026-10-16-mnt-251-session-attribution-accounting]], [[2026-10-25-mnt-258-tool-usage-stats]],
  [[2026-10-16-mnt-234-isolate-session-context]], [[2026-10-16-mnt-245-empty-session-history]],
  [[2026-10-25-session-history-cost-and-failure-reasons]]
