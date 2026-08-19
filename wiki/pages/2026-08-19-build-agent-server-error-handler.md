---
title: Build agent server error — root cause and Awaiting Input handler
date: 2026-08-19
type: debug
status: resolved
session_id: ses_fe690f0deffe9Sisjgy3YfHCGl
services: [main, workflows, agents, linear]
branch: master
tickets: [MNT-151]
tags: [build, opencode, error-handling, awaiting-input, spending-limit, server-error, linear]
related: [2026-07-21-awaiting-input-status-for-session.md, 2026-08-05-pr-creation-failure-handler.md, 2026-08-19-build-agent-stale-session-deleted-worktree.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md]
---

# Build agent server error — root cause and Awaiting Input handler

## TL;DR

The last workflow run for MNT-151 failed ~4 seconds after "Running BUILD agent" with
`Error: { "name": "UnknownError", "data": { "message": "Unexpected server error. Check server logs for details.", "ref": "err_18e38f63" } }` and exit code 1. Root cause: the OpenCode workspace
`wrk_01KE576G79X6RZGNHBTA39CPSM` hit its **$30/month spending limit**, so the opencode gateway rejects
paid-model requests (the build model `opencode-go/deepseek-v4-flash`) with a generic server 500 — the
`err_...` ref is server-side only and never appears in local logs. Fix in code: a new `BuildError`
handler in `main.py` posts a `build_failed` Linear comment and moves the ticket to `Awaiting Input`
instead of reverting it to TODO. MNT-151 was moved to `Awaiting Input` with the failure comment.

## Symptom

- Session log `sessions/a90b02f2-9fa2-4d86-91b1-8ab07bbfea87.log` (MNT-151, worktree
  `/Users/alexander/.demetra/worktrees/manti-by/coruscant/mnt-151-switch-to-redis-remove-kafka`):
  `12:49:36 Running BUILD agent` → `12:49:40 ERROR : Workflow error: Build agent failed (exit 1): Error: { ... }`
  — an instant ~4s failure, no model call ever streamed.
- MNT-151 state history shows `In Progress` (09:49:36) → `Todo` (09:49:41) — the ticket was silently
  reverted to TODO with no Linear-side trace, the failure the new handler is meant to fix.

## Step 1 — Trace the failure to the opencode CLI and gateway

`demetra/workflows/build.py:87` calls `opencode_build_agent(...)`; on non-zero exit it raises
`BuildError(f"Build agent failed (exit {exit_code}): {stderr.strip() or stdout.strip() or 'unknown error'}")`
(`build.py:95-98`). `demetra/services/agents/opencode.py:75` builds the `opencode run` command with
`--model opencode-go/deepseek-v4-flash`. In `~/.local/share/opencode/log/opencode.log` the build run
(`run=cee2e9ca`) bootstraps the worktree at 09:49:37Z and then ends with **no `stream` entry** — the
gateway rejected the request before the CLI logged a stream. The error shape
(`UnknownError` / `data.ref`) is the opencode CLI's rendering of a server-side error; `err_18e38f63`
appears nowhere in local logs.

## Step 2 — Find the workspace spending limit

The opencode log contains repeated
`AI_APICallError: Your workspace has reached its monthly spending limit of $30. Manage your limits here: https://opencode.ai/workspace/wrk_01KE576G79X6RZGNHBTA39CPSM/billing`
(seen 2026-08-10 multiple times and 2026-08-19T09:51:44Z in the current session's title agent
`gpt-5.4-nano`). The workspace `wrk_01KE576G79X6RZGNHBTA39CPSM` is shared by both `opencode` and
`opencode-go` providers (`~/.local/share/opencode/auth.json` uses one API key for both). The build
model `opencode-go/deepseek-v4-flash` is paid, so those calls 500; the free
`opencode/deepseek-v4-flash-free` used for investigation still works — which is why builds fail while
forensics sessions run.

## Step 3 — Rule out other causes

- **Not a timeout** — 4s wall-clock, far below any limit.
- **Not a local config/CLI error** — the CLI bootstrapped fine and made no stream call; error came
  from the gateway.
- **Not worktree-specific** — the same signature (`err_dfe4ce8d`, `err_8d371363`, `err_2174fc11`)
  occurred 2026-07-20 on the server for MNT-132, so this is a recurring gateway failure mode, not a
  one-off.
- Local `opencode.db` `workspace`/`account`/`credential` tables are empty — billing state is
  server-side only.

## Root cause

The OpenCode workspace reached its **$30/month spending limit**; the opencode.ai gateway returns a
generic `UnknownError: "Unexpected server error. Check server logs for details."` (with a server-side
`err_...` ref) for paid-model requests. The build agent (`opencode-go/deepseek-v4-flash`) inherits
that 500, the CLI exits 1, and Demetra's generic `DemetraError` handler reverted the ticket to TODO
with no comment.

## Resolution / Fix

**File:** `demetra/workflows/failure.py` — extracted `notify_linear_failure(context, body, comment_label)`
(posts the comment, looks up the `awaiting_input` state, updates the ticket; surfaces manual-recovery
messages on failure). Added `process_build_failure(context, error)` which renders the new
`demetra/templates/build_failed.md` template (describes the failure, flags the spending-limit and
transient-server-error possibilities) and delegates to `notify_linear_failure`.

**File:** `main.py` — added `except BuildError` before the generic `DemetraError` handler (mirroring the
existing `PullRequestError` / `ReviewError` paths): calls `process_build_failure(...)` and sets
`failure_step, should_update_linear_status = "awaiting_input", False` so cleanup does **not** revert
the ticket to TODO.

**File:** `demetra/templates/build_failed.md` — new comment template for build-agent failures.

**File:** `tests/test_failure.py` — `test_posts_build_failure_comment` asserts the comment body and the
`awaiting_input` status update. **File:** `tests/test_entrypoints.py` —
`test_main_delegates_build_failure_to_failure_step` asserts `main()` routes a `BuildError` from
`run_build_step` to `process_build_failure` and cleans up with `should_update_linear_status=False` +
`failure_step="awaiting_input"`.

**Linear:** MNT-151 moved to `Awaiting Input` with the `build_failed` comment posted (ref
`err_18e38f63`).

## Test Results

`uv run ruff check` on changed files — pass. `uv run ty check` — pass.
`uv run pytest tests/test_failure.py tests/test_entrypoints.py` — 21 passed.

## Consistency note (2026-08-19)

- A later same-day session ([[2026-08-19-build-agent-stale-session-deleted-worktree]]) found that an identical `UnknownError` signature also occurs when `--session` resumes an opencode session whose worktree was deleted by cleanup. The 12:49 failure attributed here to the spending limit may have been incomplete; post-limit retries were definitively caused by the stale session.

## Known follow-up (not fixed this session)

- Raise/reset the workspace limit at
  `https://opencode.ai/workspace/wrk_01KE576G79X6RZGNHBTA39CPSM/billing`, or set
  `OPENCODE_BUILD_MODEL` in the project environment to a free model, before re-running MNT-151.
- Optional: detect the `UnknownError` / spending-limit signature inside
  `opencode_build_agent` and raise a dedicated exception with a clearer message + retry on transient
  gateway 500s.

## Follow-ups

- None beyond the known follow-up above; the handler code is staged on `master` (not yet committed —
  awaiting explicit go-ahead).

## References

- Related: [[2026-08-05-pr-creation-failure-handler]], [[2026-08-19-build-agent-stale-session-deleted-worktree]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]], [[2026-07-21-awaiting-input-status-for-session]]
- External: [MNT-151](https://linear.app/mnt/issue/MNT-151/switch-to-redis-remove-kafka)
