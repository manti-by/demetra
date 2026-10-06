---
title: Fix code-review findings on step/status refactor
date: 2026-07-16
type: implementation
status: resolved
session_id: e6a4e432-a337-46a5-8e3a-a027d7cb0cdd
services:
- main
- api
- database
- workflows
- linear
- sessions
- opencode
branch: '-'
tickets:
- MNT-37
- MNT-63
- MNT-83
- MNT-22
tags:
- sessions
- step
- status
- code-review
- database
- refactor
- modules
- workflow
- user-scoping
- task-status
- migration
- resume
- isolation
- research
related:
- 2026-02-23-refactor-workflow-into-modular-steps.md
- 2026-04-02-link-user-tasks-sessions.md
- 2026-07-16-simplify-session-logging-setup.md
- 2026-08-05-pr-creation-failure-handler.md
- 2026-08-25-mnt-187-wiki-pages-not-generated.md
- 2026-09-01-mnt-177-research-loop.md
- 2026-06-08-session-step-attribute.md
- 2026-02-21-opencode-sessions-isolation.md
- 2026-07-21-awaiting-input-status-for-session.md
- 2026-08-05-post-build-validation.md
---
# Fix code-review findings on step/status refactor

## TL;DR

Code review of the `status`→`step` migration surfaced 4 findings — drifted duplicate step enum, `status`/`step` naming conflation in the API, stale hardcoded return in `upsert_pending_session`, and two undocumented divergent `ON CONFLICT` clauses. All fixed; 473 tests, `ruff`/`ty` clean.

---

## Overview

Diff introduced `sessions.step` (initial/plan/build/review/lint/test/push/completed/failed) as source of truth but left a duplicate vocabulary, API still named `status`, and an upsert return value not matching its SQL.

## Step 1 — Unify step vocabulary

`demetra/library/models.py:8` added `"failed"` to `StepType` (was missing though `cleanup.py` sets it). `demetra/api/sessions.py:14` replaced hardcoded `VALID_STATUSES` with `VALID_STEPS = set(get_args(StepType))`.

## Step 2 — Rename `status` → `step` end-to-end

`demetra/api/sessions.py` and `demetra/services/database.py:349` (`get_sessions`): query param `status` → `step`, error message and docstring updated. No frontend consumer passed `status` (`react/src/services/api.ts`), so rename was safe. Tests renamed `test_list_sessions_filter_by_status/invalid_status` → `..._by_step/invalid_step`.

## Step 3 — Fix `upsert_pending_session` return value

`demetra/services/database.py:84-146`: SQL already had `step = sessions.step` (preserve progress) but return hardcoded `step="initial"`. Added `RETURNING ...` and `step=row.step or "initial"` with `None` guard.

## Step 4 — Document divergent `ON CONFLICT` clauses

- `upsert_pending_session`: `step = sessions.step` — never regress an in-progress step to `"initial"` on re-upsert (idempotent create).
- `save_session`: `step = EXCLUDED.step` — always advances (marks plan reached); removed vestigial `COALESCE(EXCLUDED.step, sessions.step)` (dead code since `EXCLUDED.step` is always `"plan"`).

## Test Results

473 passed, `ruff`/`ty` clean.

---

## Source — [[2026-02-23-refactor-workflow-into-modular-steps]]

MNT-37 (2026-02-23): monolithic `main.py` split into `demetra/workflows/*.py` with unified finalize/cleanup. Basis for current layout.

## Source — [[2026-04-02-link-user-tasks-sessions]]

MNT-63 (2026-04-02): tasks/sessions user-scoped; `task_status` merged into `sessions` with `project_id`/`user_id` columns.

## Source — [[2026-06-08-session-step-attribute]]

Session step attribute for durable resume; now 13-value `StepType` including validate/awaiting_input/wiki/research.

## Follow-ups

None.

> **Updates (2026-08-18 – 2026-09-01):** `StepType` grew: `validate` (Q-001), `wiki` ([[2026-08-25-mnt-187-wiki-pages-not-generated]]), `research` ([[2026-09-01-mnt-177-research-loop]]), `awaiting_input` ([[2026-08-05-pr-creation-failure-handler]]). Current: `initial | plan | research | build | validate | review | lint | test | wiki | push | completed | failed | awaiting_input`. `demetra/services/database.py` → `demetra/services/persistence/database.py`.

> **Consistency fix (2026-09-02):** added `2026-09-01-mnt-177-research-loop.md` to `related`.

## References

- Related: [[2026-02-23-refactor-workflow-into-modular-steps]], [[2026-04-02-link-user-tasks-sessions]], [[2026-07-16-simplify-session-logging-setup]], [[2026-08-05-pr-creation-failure-handler]], [[2026-08-25-mnt-187-wiki-pages-not-generated]], [[2026-09-01-mnt-177-research-loop]], [[2026-06-08-session-step-attribute]], [[2026-02-21-opencode-sessions-isolation]], [[2026-07-21-awaiting-input-status-for-session]], [[2026-08-05-post-build-validation]]
