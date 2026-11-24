---
title: Context bloating — agents scan repo root instead of worktree
generated: {by: demetra, at: '2026-06-03T00:00:00Z'}
description: Under MNT-105, this records a context-bloating bug where plan-loop runs made the OpenCode plan agent scan the supervisor repo root instead of the isolated worktree; the root cause was subprocesses not inheriting the worktree as cwd, fixed by setting the target directory for all agents (plan, build, review, resolve) and bumping to 1.11.7; archived.
type: debug
status: deprecated
session_id: '-'
services: [subprocess, opencode, workflows]
branch: '-'
tickets: [MNT-105]
tags: [cwd, worktree, context, bug]
related: [2026-07-16-fix-empty-build-plan-loop.md, 2026-08-04-fix-resolve-agent-truncated-context.md]
---

# Context bloating — agents scan repo root instead of worktree

> **Archived on 2026-10-26.** Useful info merged into
> [2026-08-04-fix-resolve-agent-truncated-context](/pages/2026-08-04-fix-resolve-agent-truncated-context.md). See wiki/archive/ for the original.

## TL;DR

`uv run main.py --project-name mgallery --auto --plan-loop` made the OpenCode plan agent scan `/Users/alexander/www/m2/demetra` directly instead of the isolated process worktree, bloating the agent context with the whole supervisor repo. Root cause: underlying agents did not inherit the isolated worktree as their working directory. Fix: subprocess execution now sets `cwd` / the target path for all underlying agents (plan/build/review/resolve), and the OpenCode agent instructions were refined for accuracy and consistency. Version bumped to 1.11.7.

## Symptom

- Running the plan-loop pointed the OpenCode plan agent at `/Users/alexander/www/m2/demetra` — the supervisor repo root — instead of the per-process worktree.
- Agent context ballooned because it scanned files outside the isolated checkout, causing slow, noisy planning.

## Step 1 — Confirm which directory the agent scans

The plan-loop command (`uv run main.py --project-name mgallery --auto --plan-loop`) was observed reading from the repo root rather than the process worktree. The agent's scan scope was wrong: the working directory of the underlying agent subprocess was never switched to the worktree.

## Step 2 — Trace how subprocesses spawn agents

Underlying agents (plan/build/review/resolve) are launched through the subprocess runner. The runner was not propagating the isolated worktree path as the working directory, so each agent inherited the process CWD — the repo root.

## Root cause

Underlying agents did not inherit the isolated worktree as their working directory. Every agent subprocess launched without an explicit working directory resolved to the repo root, so the plan agent scanned the full supervisor repository instead of the small per-ticket worktree — context bloating.

## Resolution / Fix

**File:** subprocess runner + OpenCode agent instructions

- Subprocess execution now correctly sets `cwd` / the target path for all underlying agents: plan, build, review, and resolve.
- OpenCode agent instructions were refined for accuracy and consistency so agent behaviour matches the new directory contract.
- Version bumped to 1.11.7.

The directory-handling work here relates to the worktree-mismatch handling documented in [2026-07-16-fix-empty-build-plan-loop](/archive/2026-07-16-fix-empty-build-plan-loop.md).

---

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [2026-07-16-fix-empty-build-plan-loop](/archive/2026-07-16-fix-empty-build-plan-loop.md), [2026-08-04-fix-resolve-agent-truncated-context](/pages/2026-08-04-fix-resolve-agent-truncated-context.md)
- External: [MNT-105 — Context bloating (Linear)](https://linear.app/mnt/issue/MNT-105)
