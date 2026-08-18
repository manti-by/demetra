---
title: Git cleanup on error
date: 2026-02-15
type: implementation
status: resolved
session_id: -
services: [workflows, git]
branch: -
tickets: [MNT-19]
tags: [git, worktree, cleanup, error-handling]
related: []
---

# Git cleanup on error

## TL;DR

When a workflow fails mid-run, git state is now cleaned up automatically: a `cleanup_workflow(context, ...)` function always removes the git worktree and, when the workflow errored, additionally force-deletes the branch. Cleanup is invoked before every early return in `main.py`, and the `finally` block guards against a `None` context.

---

## Overview

Before this change a failed workflow could leave a detached worktree and an orphan branch behind. MNT-19 adds deterministic cleanup on every exit path so failed runs do not leak git state.

## Step 1 — Add `cleanup_workflow`

**File:** `demetra/workflows/` git cleanup logic

```python
def cleanup_workflow(context, errored: bool, ...) -> None:
    git_worktree_remove(...)          # always
    if errored:
        git_branch_delete(...)        # -D on error
```

`git worktree remove` is always called; `git branch -D` only when the workflow errored (successful runs keep the branch for PR creation).

## Step 2 — Wire cleanup into every early return

**File:** `main.py`

Every early-return path in the main workflow now invokes `cleanup_workflow` before exiting, and the `finally` block also calls it — guarded against a `None` context to avoid the "critical context null reference" crash during teardown.

## Step 3 — Later hardening

Subsequent work (MNT-105 / PR #46) hardened this further to handle the case where a worktree already exists when starting a run.

## Test Results

Verified through workflow runs that intentionally fail and exit early; the worktree and branch are removed on each error path. Automated coverage for cleanup behavior exists in the workflow tests added alongside MNT-21.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-19
