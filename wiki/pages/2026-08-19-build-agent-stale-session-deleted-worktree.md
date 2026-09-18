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
related:
- 2026-08-19-build-agent-server-error-handler.md
- 2026-07-15-duplicated-log-messages.md
- 2026-09-16-mnt-205-revise-merged-environment.md
---

# Build agent UnknownError — stale opencode session bound to deleted worktree

## TL;DR

After the spending limit was raised, MNT-151 kept failing with `UnknownError: Unexpected server error (err_...)` — not the limit but a stale `sessions.session_id` (`ses_fe96234f1ffeADBso4qFrnzE0Y`) bound to a worktree deleted by cleanup. Every retry passed `--session <stale-id>` and the server 500s when the session directory is gone. Fixed by nulling `session_id` in the DB; env vars were not the cause.

## Symptom

- `Build agent failed (exit 1): {UnknownError, ref err_f9972a06}` at 13:15 and `err_28589456` at 13:40 after raising the limit — ~5s after worktree creation, no model stream (`sessions/a90b02f2-9fa2-4d86-91b1-8ab07bbfea87.log`).

## Investigation

**Spending limit ruled out** — Direct `opencode run --model opencode-go/deepseek-v4-flash` works. `demetra/.env` still has paid `OPENCODE_*`; DB `project_environment` has no model overrides. `err_...` refs absent under `~/.local/share/opencode/` (server-side only).

**Repro with exact Demetra invocation** — `demetra/workflows/build.py:87-94` calls `opencode_build_agent(..., session_id=context.session_id)` → `opencode run --dir <new worktree> --session ses_fe96234f...`. Without `--session`: exit 0. With stale session: `UnknownError` (`err_b3c6f994`) reproduced. Faithful repro: create session in dir A, `rm -rf` A, continue from dir B → `UnknownError` (`err_50227666`). A deleted-directory session can never be resumed.

**Why stale** — `opencode.db` session `ses_fe96234f...` has `directory=/.../worktrees/.../mnt-151-switch-consumer-py-to-redis-pub-sub-remove-kafka` — gone after cleanup (`Removing worktree`/`Deleting branch` in `demetra.log`). Title/slug changed so new worktrees get a different name. Opencode log `run=5b2b452e` shows `failed to initialize fff: Invalid path ...` then dies before `stream`. `main.py:105` skips plan when `context.session.build_plan` is set, so every retry goes straight to build with poisoned `--session`.

## Root cause

Demetra persists `sessions.session_id` but cleanup deletes its worktree. Opencode 1.18.18 cannot resume a session whose directory is gone and returns generic 500, so a once-failed task can never be retried until the session is cleared.

## Resolution

`UPDATE sessions SET session_id = NULL, step = 'initial' WHERE task_id = 'a90b02f2-...'` — keeps stored `build_plan` so next run skips re-planning but starts a fresh opencode session.

## Known follow-up (not fixed this session)

- Systemic fix: clear `sessions.session_id` when cleanup deletes worktree, or catch `UnknownError` in `opencode_build_agent` and retry once without `--session`. Other rows (`ses_013d53a7...`, etc.) have same latent risk.
- Earlier 12:49 attribution to spending limit ([[2026-08-19-build-agent-server-error-handler]]) was incomplete — stale session produces identical signature.

## Follow-ups

- Decide on systemic fix (clear on cleanup vs retry without `--session`) and implement.

> **Status update (2026-08-28, Consistency Agent):** Re-checked `demetra/workflows/cleanup.py` and `demetra/services/vcs/git.py` after PR #106 (MNT-189) — no code clears `sessions.session_id` on worktree deletion; `opencode_build_agent` still passes `--session` when `context.session_id` is set. Follow-up remains open.

> **Status update (2026-09-11, Consistency Agent):** Re-checked `demetra/workflows/cleanup.py` and `demetra/services/agents/opencode.py:87` — systemic fix still not implemented; failure mode remains latent.

> **Consistency note (2026-09-15, Consistency Agent):** Re-verified `demetra/workflows/cleanup.py` and `demetra/services/agents/opencode.py:92` on branch `mnt-204-research-result-modal` — no `session_id` clear on cleanup, `opencode_build_agent(session_id=context.session_id)` still passes stale id; systemic retry/clear still not implemented — latent. See follow-up above.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-19-build-agent-server-error-handler]], [[2026-07-15-duplicated-log-messages]]
- External: [MNT-151](https://linear.app/mnt/issue/MNT-151/switch-to-redis-remove-kafka)

> **Status update (2026-09-16, MNT-205):** The model resolution path described
> here (`_resolve_opencode_model`) was replaced by
> `context.environment.opencode_build_model` on the shared
> `SessionEnvironment` resolver. See
> [[2026-09-16-mnt-205-revise-merged-environment]].
