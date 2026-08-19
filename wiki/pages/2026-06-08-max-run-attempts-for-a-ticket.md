---
title: Max run attempts for a ticket
date: 2026-06-08
type: implementation
status: resolved
session_id: "-"
services: [database, workflows, linear]
branch: "-"
tickets: [MNT-100]
tags: [run-attempts, guard, sessions, linear]
related: [2026-07-21-rich-markuperror-and-run-attempts.md]
---

# Max run attempts for a ticket

## TL;DR

Added a `run_attempts` counter to the `sessions` table and a `MAX_RUN_ATTEMPTS` project setting (default 3) so a Linear ticket cannot trigger an infinite chain of workflow runs. When the counter reaches the max the workflow is not run — the ticket is moved to `Awaiting Input` and a "Max run attempts reached" comment is posted. Basic tests added. The counter was later refined to only increment on actual failure (see [[2026-07-21-rich-markuperror-and-run-attempts]]).

> **Status update (2026-08-04, Consistency Agent):** the `MAX_RUN_ATTEMPTS` default is now
> `5` in `demetra/settings.py` (changed in `8ffc53b`, 2026-07-20); "default 3" below reflects
> the original implementation. The increment semantics were also corrected to count only
> actual failures — see [[2026-07-21-rich-markuperror-and-run-attempts]].

---

## Overview

Workflow runs for a single Linear ticket were unbounded: the watcher re-triggered runs whenever a session was not done. This change adds a per-session attempt guard so a persistently failing ticket stops consuming the queue.

- `sessions.run_attempts` — new integer counter, incremented on actual failure only (not every run; corrected in [[2026-07-21-rich-markuperror-and-run-attempts]]).
- `MAX_RUN_ATTEMPTS` — project setting, default 5 (originally 3; changed in `8ffc53b`).
- When the counter exceeds `MAX_RUN_ATTEMPTS` (the check is `>`, not `==`): the workflow is skipped, the ticket moves to `Awaiting Input`, and the bot posts "Max run attempts reached".

## Step 1 — Persist run attempts on the session

**File:** `sessions` table

Added the `run_attempts` field to the `sessions` model. Each watcher-triggered workflow run increments the counter for that ticket's session.

## Step 2 — Cap runs via project settings

**File:** project settings

Added `MAX_RUN_ATTEMPTS` (default 3). Before spawning the workflow subprocess the watcher compares the session counter against the max; at the cap it bails instead of running.

## Step 3 — Surface the cap on the ticket

When the counter exceeds `MAX_RUN_ATTEMPTS` (the guard is `run_attempts > MAX_RUN_ATTEMPTS`):

- the workflow is not run,
- the Linear ticket is moved to the `Awaiting Input` state,
- a comment "Max run attempts reached" is posted.

## Test Results

Basic tests added covering the increment path and the cap-triggered bail-out (comment posted, ticket moved, no workflow run). The increment semantics were later corrected so only actual failures count — see [[2026-07-21-rich-markuperror-and-run-attempts]].

---

## Follow-ups

None.

## References

- Related: [[2026-07-21-rich-markuperror-and-run-attempts]]
- External: [MNT-100 — Max run attempts for a ticket (Linear)](https://linear.app/mnt/issue/MNT-100)
