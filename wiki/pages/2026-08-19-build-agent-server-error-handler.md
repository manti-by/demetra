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

MNT-151 builds failed ~4s after "Running BUILD agent" with `UnknownError: Unexpected server error (err_...)` exit 1. Initially traced to the $30/month spending limit on workspace `wrk_01KE576G79X6RZGNHBTA39CPSM` blocking paid model `opencode-go/deepseek-v4-flash`, but the same signature also occurs on stale-session retries (worktree deleted by cleanup) — see [[2026-08-19-build-agent-stale-session-deleted-worktree]]. Fixed by routing `BuildError` to `Awaiting Input` with a `build_failed` Linear comment instead of silently reverting to TODO.

## Symptom

- `sessions/a90b02f2-9fa2-4d86-91b1-8ab07bbfea87.log`: `12:49:36 Running BUILD agent` → `12:49:40 ERROR: Build agent failed (exit 1): {UnknownError, ref err_18e38f63}` — no model stream, ~4s.
- Ticket history: `In Progress` (09:49:36) → `Todo` (09:49:41) with no Linear comment — the gap the fix closes.

## Investigation

**Opencode CLI/gateway** — `demetra/workflows/build.py:87` calls `opencode_build_agent(...)` (`demetra/services/agents/opencode.py:75`, `--model opencode-go/deepseek-v4-flash`); on non-zero exit raises `BuildError` (`build.py:95-98`). In `~/.local/share/opencode/log/opencode.log` the run `cee2e9ca` bootstraps the worktree then ends with no `stream` entry — gateway rejected before CLI streamed. `err_...` refs are server-side only, absent locally.

**Spending limit** — Log shows `AI_APICallError: Your workspace has reached its monthly spending limit of $30` (2026-08-10 and 2026-08-19T09:51:44Z). Workspace `wrk_01KE576G79X6RZGNHBTA39CPSM` shares one API key for `opencode`/`opencode-go` (`auth.json`); paid `opencode-go/deepseek-v4-flash` 500s while free `opencode/deepseek-v4-flash-free` still works.

**Ruled out:** timeout (4s), local CLI/config error (CLI bootstrapped fine, no stream), worktree-specific (same `err_dfe4ce8d`/`err_8d371363`/`err_2174fc11` on MNT-132, 2026-07-20). Local `opencode.db` workspace/account/credential tables empty — billing is server-side.

## Root cause

Gateway returns generic `UnknownError: Unexpected server error (err_...)` for paid-model calls when the workspace hits its $30 limit; `BuildError` was caught by the generic `DemetraError` handler which reverted to TODO with no comment. Identical `UnknownError` also occurs when retrying with a persisted `sessions.session_id` whose worktree was deleted by cleanup — post-limit retries (13:15, 13:40) were that second cause.

## Resolution

- `demetra/workflows/failure.py` — extracted `notify_linear_failure(context, body, comment_label)` and added `process_build_failure(context, error)` rendering `demetra/templates/build_failed.md` (spending-limit + transient-error guidance).
- `main.py` — added `except BuildError` before generic `DemetraError` (mirrors `PullRequestError`/`ReviewError`), calls `process_build_failure` and sets `failure_step, should_update_linear_status = "awaiting_input", False`.
- `demetra/templates/build_failed.md` — new `build_failed` comment template.
- Tests: `tests/test_failure.py:test_posts_build_failure_comment`, `tests/test_entrypoints.py:test_main_delegates_build_failure_to_failure_step`.
- Linear: MNT-151 moved to `Awaiting Input` with `build_failed` comment (`err_18e38f63`).

## Test Results

`ruff check` / `ty check` pass; `uv run pytest tests/test_failure.py tests/test_entrypoints.py` — 21 passed.

## Consistency note (2026-08-19)

Same `UnknownError` also occurs when `--session` resumes a deleted-worktree session — see [[2026-08-19-build-agent-stale-session-deleted-worktree]]. Before retrying MNT-151, clear stale session (`sessions.session_id = NULL`, keep `build_plan`) or start fresh.

## Known follow-up (not fixed this session)

Before re-running MNT-151 clear stale session as above, then address limit: raise/reset at `https://opencode.ai/workspace/wrk_01KE576G79X6RZGNHBTA39CPSM/billing` or set `OPENCODE_BUILD_MODEL` to a free model. Optional systemic fix: detect `UnknownError`/spending-limit/stale-session in `opencode_build_agent` and retry once without `--session`.

## Follow-ups

- None beyond the known follow-up above.

## Consistency note (2026-08-20)

`BuildError` handler (`process_build_failure` in `demetra/workflows/failure.py`, wired in `main.py:158`) merged via PR #82 (2026-08-19) on `master`.

## References

- Related: [[2026-08-05-pr-creation-failure-handler]], [[2026-08-19-build-agent-stale-session-deleted-worktree]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]], [[2026-07-21-awaiting-input-status-for-session]]
- External: [MNT-151](https://linear.app/mnt/issue/MNT-151/switch-to-redis-remove-kafka)
