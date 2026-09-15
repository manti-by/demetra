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

Same-run halt after posting questions works (`move_to_awaiting_input` raises `AutoCancelledError`), but the signal is not durable: the questions-run persists `build_plan` before posting questions and never re-checks Linear/`awaiting_input` on resume. When the ticket returns to TODO, the next run sees a non-empty `build_plan` (`main.py:105`), skips `run_plan_step`, posts the stale plan and proceeds through build→validate→review→PR with questions unanswered. A watcher race (enqueue every TODO poll, `pending_ids` dedupes only upsert/Linear move not enqueue) can also let a second run reach review while the first parks the ticket.

## Symptom

Questions comment posted and ticket moved to `Awaiting Input`, yet workflow still proceeds to review and creates a PR.

## Same-run halt (works)

`demetra/workflows/plan.py:21-41` — `move_to_awaiting_input` updates Linear, sets `sessions.step="awaiting_input"`, raises `AutoCancelledError` caught in `main.py` → `failure_step="awaiting_input"`, cleanup leaves ticket in Awaiting Input and removes worktree. Verified in `sessions/0dbaf2d0….log` (MNT-132). Questions path has raised since `ff23355` (2026-03-04).

## Questions-run persists stale plan

`demetra/workflows/plan.py:117-126,150,185` — `save_session(build_plan=...)` runs before `extract_questions` / `move_to_awaiting_input`. Row ends with `build_plan` set, `posted_to_linear=False`, `step="awaiting_input"` — stored as final though never approved.

## Resume skips planning

`main.py:105-106,117-124`:
```python
if not context.session or not context.session.build_plan:
    if not await run_plan_step(context=context):
        return
```
Ticket back to TODO → `build_plan` non-empty → `run_plan_step` skipped → stale plan posted (`posted_to_linear` was False) → `run_build_step` runs full loop including review (`demetra/workflows/build.py:132`). Test `test_main_skips_replan_when_build_plan_already_present` (`tests/test_entrypoints.py`) locks skip for `step="build"`; `awaiting_input` never considered, no test for questions-then-retrigger.

## Duplicate-enqueue race

`demetra/services/daemons/watcher.py:136-165` — `process_tasks` enqueues every TODO task every poll; `pending_ids` guards only upsert + `in_progress` move (line 144), not `delay_run_workflow` (line 165). If move fails/lags or ticket sits in TODO across ≥2 polls, second run is queued; run A parks in Awaiting Input while run B (4 RQ workers) proceeds to PR.

## Root cause

Awaiting Input is one-shot, not a durable gate: plan persisted as final, `main.py` never re-checks Linear state (unconditionally moves to `in_progress`), watcher dedupes bookkeeping not enqueue.

## Resolution (recommended, not yet implemented)

- **Primary:** in `main.py:105` re-run plan when `context.session.step == "awaiting_input"` (like existing `step="failed"` replan, `test_main_replans_when_step_failed_but_build_plan_empty`), optionally clear/avoid persisting plan in questions path.
- **Secondary:** in `watcher.py:165` skip `delay_run_workflow` for already-pending tasks / track in-flight runs.

## Known follow-up

Fix not implemented — diagnosis only. Verify questions→TODO→new run re-runs `run_plan_step` without reaching `run_review_agents`. Log note: interleaved per-task logs (`64a5d351…`, etc.) are pytest output (`testserver`, faker titles), not production.

## Follow-ups

- Implement `awaiting_input` replan guard + watcher enqueue dedupe.

> **Status update (2026-09-01):** Both fixes still not implemented (verified: `main.py` gates only on `not build_plan`, `process_tasks` still enqueues every TODO poll unconditionally). MNT-183 (`dfd64f6`, 2026-09-01) moved `in_progress` outside `pending_ids` guard — mitigates one race trigger but ≥2 polls still double-enqueue; primary `awaiting_input` guard unchanged. See [[2026-08-28-mnt-191-ticket-status-not-changed]].

> **Consistency fix (2026-09-02):** Quoted `branch: -` → `"-"`; added `2026-08-28-mnt-191-ticket-status-not-changed.md` to `related`.

> **Consistency note (2026-09-11):** Re-verified on current master (`main.py:127`, `watcher.py:165`): both fixes still not implemented.

> **Consistency note (2026-09-15, Consistency Agent):** Re-verified `main.py:127` (`if not context.session or not context.session.build_plan`) and `demetra/services/daemons/watcher.py:165` — replan guard on `awaiting_input` and watcher enqueue dedupe still not implemented on this branch; awaiting product decision. Diagnosis in this page remains current.

## References

- Related: [[2026-07-21-awaiting-input-status-for-session]], [[2026-08-19-build-agent-server-error-handler]], [[2026-08-24-guard-empty-plan-output]], [[2026-08-05-pr-creation-failure-handler]], [[2026-08-28-mnt-191-ticket-status-not-changed]]
