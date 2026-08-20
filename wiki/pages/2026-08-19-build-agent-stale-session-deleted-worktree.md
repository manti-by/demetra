---
title: Build agent UnknownError — stale opencode session bound to deleted worktree
date: 2026-08-19
type: debug
status: resolved
session_id: ses_fe66890faffe4nIU8hRlC6JC1H
services: [main, workflows, agents, opencode]
branch: master
tickets: [MNT-151]
tags: [build, opencode, error-handling, session-resume, worktree, server-error]
related: [2026-07-15-duplicated-log-messages.md, 2026-08-19-build-agent-server-error-handler.md]
---

# Build agent UnknownError — stale opencode session bound to deleted worktree

## TL;DR

After the opencode spending limit was raised, MNT-151 builds kept failing with the same
`UnknownError: "Unexpected server error"` (`err_...` ref). Root cause this time: Demetra's
`sessions.session_id` for the task still pointed at opencode session `ses_fe96234f1ffeADBso4qFrnzE0Y`,
which is bound to worktree `mnt-151-switch-consumer-py-to-redis-pub-sub-remove-kafka` — deleted by
cleanup after the first failed run (the ticket title/slug also changed, so new worktrees get a new
name). Every retry passed `--session <stale-id>` and the opencode server 500s when the session's
directory no longer exists. Reproduced from scratch; fixed by nulling the session row. Environment
variables were **not** the problem.

## Symptom

- `Build agent failed (exit 1): Error: { "name": "UnknownError", "data": { "message": "Unexpected server error...", "ref": "err_f9972a06" } }` at 13:15, and again at 13:40 (`err_28589456`) after the user raised the spending limit and set free models.
- Session log `sessions/a90b02f2-9fa2-4d86-91b1-8ab07bbfea87.log`: failure ~5s after worktree creation, no model call streamed.

## Step 1 — Rule out the spending limit and model config

- Direct CLI test with the paid build model: `opencode run --model opencode-go/deepseek-v4-flash` →
  works. The raised limit is in effect.
- `demetra/.env` still has paid `OPENCODE_*` models; the DB `project_environment` user-scope rows have
  no model overrides; no project-scope rows at all. The user's "free models" never reached Demetra's
  resolution path (`_resolve_opencode_model`, `demetra/services/agents/opencode.py:17`: DB user env →
  `settings.OPENCODE` from process env). Irrelevant either way — the paid model works.
- The `err_...` refs appear nowhere under `~/.local/share/opencode/` — they are server-side only.

## Step 2 — Reproduce with the exact Demetra invocation

`demetra/workflows/build.py:87-94` calls `opencode_build_agent(..., session_id=context.session_id)` →
`opencode run --dir <new worktree> --model ... --agent build-agent --session ses_fe96234f... --title ...`.

- Without `--session`: works (exit 0, answer streamed).
- With `--session ses_fe96234f1ffeADBso4qFrnzE0Y`: `UnknownError` (`err_b3c6f994`) — reproduced.
- Faithful repro: create session in temp dir A, `rm -rf` A, continue the session from dir B →
  `UnknownError` (`err_50227666`). **A session whose directory was deleted can never be resumed.**

## Step 3 — Trace why the session is stale

- `sqlite3 ~/.local/share/opencode/opencode.db`: session `ses_fe96234f...` has
  `directory=/Users/alexander/.demetra/worktrees/manti-by/coruscant/mnt-151-switch-consumer-py-to-redis-pub-sub-remove-kafka`.
- That worktree is gone — cleanup (`Removing worktree` / `Deleting branch` in demetra.log) deletes it
  after every failed run, and the Linear title change (`...consumer.py to Redis pub/sub...` →
  `Switch to Redis, remove Kafka`) changed the slug, so new worktrees get a different name anyway.
- opencode log for the failing run (`run=5b2b452e`): creates an instance for both the new worktree and
  the session's deleted directory (`failed to initialize fff: Invalid path ...`), starts
  `loop ... step=0`, then dies before any `stream` entry.
- `main.py:105` skips the plan step when `context.session.build_plan` is set (it is, stored in the DB
  row), so every retry goes straight to the build step with the poisoned `--session`.

## Root cause

Demetra persists the opencode session id per task (`sessions.session_id`) but cleanup deletes the
worktree the session belongs to. opencode 1.18.18 cannot resume a session whose directory no longer
exists and returns a generic 500 instead of a useful error, so a task that fails once after planning
can never be retried — every rerun fails identically a few seconds into the build step.

## Resolution / Fix

- `UPDATE sessions SET session_id = NULL, step = 'initial' WHERE task_id = 'a90b02f2-...'` — the stored
  `build_plan` is kept, so the next run skips re-planning and the build agent starts a fresh opencode
  session in the new worktree.

## Known follow-up (not fixed this session)

- Code fix (systemic): clear `sessions.session_id` when cleanup deletes the worktree, or catch the
  `UnknownError` signature in `opencode_build_agent` and retry once without `--session`. Other old
  rows in `sessions` (`ses_013d53a7...`, `ses_01451c57...`, etc.) have the same latent problem if their
  tasks are re-run.
- Earlier same-day attribution of the 12:49 failure to the spending limit
  ([[2026-08-19-build-agent-server-error-handler]]) was at best incomplete — the stale session produces
  the identical signature, and the limit error was only proven for the title agent.

## Follow-ups

- Decide on the systemic fix (clear session on cleanup vs. retry without `--session`) and implement.

## References

- Related: [[2026-08-19-build-agent-server-error-handler]], [[2026-07-15-duplicated-log-messages]]
- External: [MNT-151](https://linear.app/mnt/issue/MNT-151/switch-to-redis-remove-kafka)
