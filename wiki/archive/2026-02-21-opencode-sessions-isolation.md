---
title: OpenCode sessions isolation
date: 2026-02-21
type: investigation
status: resolved
session_id: -
services: [opencode]
branch: -
tickets: [MNT-22]
tags: [sessions, isolation, research]
related: []
---

# OpenCode sessions isolation

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-08-session-step-attribute]]. See wiki/archive/ for the
> original.

## TL;DR

Research ticket to determine whether parallel workflows collide on OpenCode sessions. Outcome: OpenCode `run` accepts a custom `--session` / session id, which Demetra now passes for every workflow step so parallel workflows never share state. The session id is stored on the `sessions` table and later reused for log streaming and compaction.

---

## Net effect

Plan / build / review agents run under an explicit per-session id (`ses_...`). This unblocked concurrent workflows and enabled later features built on per-session state: session history, compaction, and log isolation (MNT-54).

## Investigation — how OpenCode sessions work

- OpenCode persists conversation state per session; without an explicit id, each invocation would create or reuse an implicit session, risking cross-workflow collisions.
- The `run` command accepts a custom `--session` / session id, giving the caller deterministic control over which session each workflow step uses.

## Implementation — thread the session id through

**File:** `demetra/services/opencode.py` and workflow steps

- The session id is generated once per workflow run and passed to every `opencode run` invocation (plan, build, review).
- The id is stored on the `sessions` table row for that run, making it the durable link between the workflow and its OpenCode sessions.
- Parallel workflows each get a distinct id, so their session state cannot collide.

## Open questions

- None from this ticket; follow-up tickets were created to track the features that this isolation unblocks (session history, compaction, log isolation).

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-22
