---
title: Workflow proceeds to review after ticket moved to Awaiting Input
date: 2026-08-28
type: debug
status: open
session_id: ses_fb7885e31ffehP8M22apgonwNj
services: [main, watcher, workflows]
branch: "-"
tickets: []
tags: [awaiting-input, linear, plan, workflow, review, build-plan, resume, duplicate-enqueue]
related: [2026-07-21-awaiting-input-status-for-session.md, 2026-08-19-build-agent-server-error-handler.md, 2026-08-24-guard-empty-plan-output.md, 2026-08-05-pr-creation-failure-handler.md, 2026-08-28-mnt-191-ticket-status-not-changed.md]
---

# Workflow proceeds to review after ticket moved to Awaiting Input

## TL;DR

The same-run halt after posting questions works (`move_to_awaiting_input` raises `AutoCancelledError`), but the stop signal is not durable: the questions-run persists the `build_plan` **before** questions are posted, and the workflow never re-checks the Linear state or the `awaiting_input` session step on a later run. When the ticket returns to TODO, the next run skips the plan step entirely (`main.py:105` sees a non-empty `build_plan`), posts the stale plan as a Linear comment and proceeds to build → validate → review → PR with questions never answered. A secondary race (watcher enqueues a run on every TODO poll; `pending_ids` dedupes only the upsert/Linear move, not the enqueue) can also leave a second run free to reach review while the first parks the ticket in Awaiting Input.

---

## Symptom

In some cases, after the bot posts a comment and moves the ticket to `Awaiting Input`, the workflow is not stopped and proceeds to the review step (and creates a PR). From Linear's perspective: questions comment posted, ticket parked in Awaiting Input, yet a review/PR still happens.

## Step 1 — Same-run halt is airtight in current code

**File:** `demetra/workflows/plan.py:21-41`

`move_to_awaiting_input` updates the Linear status, sets `sessions.step = "awaiting_input"` and **raises `AutoCancelledError`**, which `main.py` catches (`except AutoCancelledError` → `failure_step, should_update_linear_status = "awaiting_input", False`) so cleanup leaves the ticket in Awaiting Input and removes the worktree. Verified in real run logs: `sessions/0dbaf2d0….log` (MNT-132) shows `Task moved to Awaiting Input state.` → `ERROR : User cancelled, exiting the workflow.` → worktree/branch cleanup. The questions path has raised since `ff23355` (2026-03-04).

## Step 2 — Questions-run persists the plan as final

**File:** `demetra/workflows/plan.py:117-126,150,185`

`save_session(build_plan=...)` runs **before** `extract_questions` and before `move_to_awaiting_input`. So the Awaiting Input session row ends with: `build_plan` set, `posted_to_linear = False`, `step = "awaiting_input"`. The plan was never approved and its questions were never answered, but it is stored as if final.

## Step 3 — Resume run skips planning and goes straight to review

**File:** `main.py:105-106,117-124`

```python
if not context.session or not context.session.build_plan:
    if not await run_plan_step(context=context):
        return
```

When the ticket returns to TODO (human re-triggers after seeing the questions) and the watcher re-runs it, `context.session.build_plan` is non-empty → `run_plan_step` is **skipped** → the stale plan is posted to Linear as a comment (`posted_to_linear` was False, `main.py:117-118`) → `run_build_step` runs the full loop including review (`demetra/workflows/build.py:132`). The open questions are never incorporated.

Existing test `test_main_skips_replan_when_build_plan_already_present` (`tests/test_entrypoints.py`) locks in the skip for `step="build"` — the `awaiting_input` step was never considered, and no test covers the questions-then-retrigger flow.

## Step 4 — Secondary race: duplicate enqueues

**File:** `demetra/services/daemons/watcher.py:136-165`

`process_tasks` enqueues a run for **every** task in every TODO poll; `pending_ids` only guards the session upsert + `in_progress` Linear move (line 144), not `delay_run_workflow` (line 165). If the `in_progress` move fails/lags or the ticket sits in TODO across ≥2 polls, a second run is queued. Run A posts questions and parks the ticket in Awaiting Input; run B (RQ runs 4 workers) proceeds through plan → build → review → PR.

## Root cause

The Awaiting Input state is a **one-shot signal**, not a durable gate:

1. The plan persisted before questions were posted is treated as final — nothing clears `build_plan` / forces re-planning when `step == "awaiting_input"`.
2. `main.py` never re-checks the ticket's current Linear state (it unconditionally moves to `in_progress` at start).
3. The watcher dedupes session bookkeeping but not run enqueueing.

## Resolution / Fix (recommended, not yet implemented)

- **Primary:** in `main.py:105`, re-run the plan step when `context.session.step == "awaiting_input"` (mirroring the existing `step="failed"` replan handling in `test_main_replans_when_step_failed_but_build_plan_empty`), so a re-triggered ticket re-plans with its Linear comments instead of building an unapproved plan. Optionally also clear/avoid persisting the plan in the questions path.
- **Secondary:** in `watcher.py:165`, skip `delay_run_workflow` for already-pending tasks (or track in-flight runs) to close the duplicate-run race.

## Known follow-up

- Fix not implemented — this session was diagnosis only.
- If the fix is the `awaiting_input` replan guard, verify: questions run → ticket back to TODO → new run re-runs `run_plan_step` and does **not** reach `run_review_agents` before questions are resolved.
- Log archaeology note: "non-halting" sequences in `/var/log/demetra` per-task session logs (`64a5d351…`, `deb0c49e…`, …) are interleaved pytest-suite output (shared fake task ids, `testserver` HTTP, faker ticket titles) — not production behavior.

---

## Follow-ups

- Implement the `awaiting_input` replan guard + watcher enqueue dedupe (see Resolution/Fix).

> **Status update (2026-09-01, Consistency Agent):** both fixes are still **not implemented**
> (re-verified on current master: `main.py` still gates the plan step only on
> `not context.session.build_plan` with no `awaiting_input`/Linear-state re-check, and
> `process_tasks` still calls `delay_run_workflow` unconditionally for every TODO task on
> every poll). MNT-183 (commit `dfd64f6`, 2026-09-01) changed one premise of Step 4: the
> `in_progress` Linear move now happens on **every** poll (outside the `pending_ids` guard),
> so the "in_progress move fails/lags" trigger of the duplicate-run race is partially
> mitigated — but a ticket sitting in TODO across ≥2 polls still enqueues a second run, and
> the missing `awaiting_input` replan guard (primary cause) is unchanged. See
> [[2026-08-28-mnt-191-ticket-status-not-changed]] for the MNT-191 form of the same block.

> **Consistency fix (2026-09-02):** fixed `branch: -` YAML parse error (quoted as `"-"`) and added `2026-08-28-mnt-191-ticket-status-not-changed.md` to `related` to mirror body link.

## References

- Related: [[2026-07-21-awaiting-input-status-for-session]], [[2026-08-19-build-agent-server-error-handler]], [[2026-08-24-guard-empty-plan-output]], [[2026-08-05-pr-creation-failure-handler]], [[2026-08-28-mnt-191-ticket-status-not-changed]]
