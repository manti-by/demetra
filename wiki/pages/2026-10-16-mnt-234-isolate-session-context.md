---
title: "MNT-234: Isolate session context"
date: 2026-10-16
type: investigation
status: resolved
session_id: "-"
services: [agents, workflows, persistence]
branch: "-"
tickets: [MNT-234, MNT-251, MNT-246, MNT-151]
tags: [sessions, session-context, plan-loop, fork, stale-session, isolation]
related: [2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-opencode-v2-session-token-accounting.md, 2026-08-19-build-agent-stale-session-deleted-worktree.md]
---

# MNT-234: Isolate session context

## TL;DR

Research into whether Demetra's agents should run in isolated opencode sessions. It concluded that only **build resumes plan's session** — every other agent already runs fresh — and that the plan→build pair is the textbook "cognitive locality" case that should stay connected via `--fork`, not full isolation. Two concrete defects it surfaced are now fixed by [[2026-10-16-mnt-251-session-attribution-accounting]]: the plan-loop stale session id and the stale-pointer-after-worktree-deletion failure. This page records the findings so the corrections live in the wiki, not only in the ticket.

---

## Net effect

The ticket's premise ("almost all agents share the same session") was wrong in count — only build shares plan's session — but right in effect: that one shared session is the longest-lived, accumulates the whole build loop plus every retry, was the only session tracked in DB/token accounting, and already caused a production incident. The literature-backed middle ground is `--fork`: build starts from a copy of plan's context under its own session id, giving continuity for build and an untouched planning record.

## Session behaviour (verified against master)

- **plan-agent** — fresh session per run (`--title` set, no `--session`); discovered afterwards by title match and persisted to `sessions.session_id`.
- **build-agent** — resumes the plan session (`--session context.session_id`); all build-loop iterations accumulate in it.
- **validate-agent** — fresh session per run.
- **review-agents** — fresh session per model per round.
- **resolve / research / merge / review-fixes** — fresh session per run (no `session_id` parameter at all).

## Defects surfaced

- **Plan-loop stale session id** — `plan.py:111` only looked up the session when `context.session_id` was empty, so in `--plan-loop` mode iteration 2 never re-resolved and the persisted id kept pointing at plan session #1. **Fixed by MNT-251:** every plan run now captures its session via the unique title and marks it primary, updating `context.session.session_id` on each iteration.
- **Stale session after worktree deletion** — a session bound to a deleted worktree can never be resumed; opencode returns a generic 500. **Fixed by MNT-251:** `cleanup_workflow` calls `invalidate_agent_sessions`, and history resolves by `task_id` so the pointer being stale no longer hides history. See [[2026-08-19-build-agent-stale-session-deleted-worktree]].
- **Title-match discovery is heuristic** — fragile once per-agent sessions multiply same-directory sessions. MNT-251 keeps title matching but bounds it with unique per-invocation titles (including `(fork #N)` handling).

## Corrections (2026-10-16)

- The "open MNT-151 follow-up" reference is **wrong** — MNT-151 is *Switch to Redis, remove Kafka* in the unrelated `coruscant` project. The stale-session follow-up is [[2026-08-19-build-agent-stale-session-deleted-worktree]], now closed by MNT-251 Phase 2 step 8.
- The `opencode agent list` command this report relied on **does not exist in v2**; the replacement is `opencode debug agents`, which is itself unusable as a preflight (project-scoped, blind to the global install). See [[2026-10-16-opencode-v2-session-token-accounting]].
- Risk #2 (`--fork` compatibility) is resolved — `--fork` exists on v2. Risk #5 (`--format json` session-id capture) is resolved — the key is still `sessionID` and is present on every event including `error`.

## Follow-ups

- None — the actionable items shipped in MNT-251.

## References

- Related: [[2026-10-16-mnt-251-session-attribution-accounting]] — the implementation that fixed the two defects
- Related: [[2026-10-16-opencode-v2-session-token-accounting]] — the v2 ground truth that corrected this report
- Related: [[2026-08-19-build-agent-stale-session-deleted-worktree]] — the incident this report misattributed to MNT-151
- External: https://linear.app/mnt/issue/MNT-234
