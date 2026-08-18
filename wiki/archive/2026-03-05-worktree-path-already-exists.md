---
title: Worktree path already exists
date: 2026-03-05
type: implementation
status: resolved
session_id: -
services: [workflows, git]
branch: -
tickets: [MNT-47]
tags: [git, worktree, bug]
related: []
---

# Worktree path already exists

## TL;DR

Fixed `create_worktree` so a stale worktree no longer raises `RuntimeError: Worktree path already exists`. The helper now detects an existing worktree reference/path and cleans it up before creating a fresh one. Later hardened again (PR #48 / MNT-105 era) for different worktree reference types. Tests included.

---

## Overview

On re-runs, an abandoned worktree from a prior run made `create_worktree` blow up instead of recovering. MNT-47 makes worktree creation idempotent against leftover state.

## Step 1 — Reproduce the crash

**File:** `create_worktree`

Creating a worktree at a path that still exists throws:

```text
RuntimeError: Worktree path already exists
```

This happened when a prior workflow run was cleaned up incompletely (or the run crashed before cleanup).

## Step 2 — Detect and clean existing worktrees first

**File:** `demetra/workflows/` worktree helper

Before creating a fresh worktree, `create_worktree` now checks for an existing worktree reference/path for the branch and removes it (mirroring the MNT-19 cleanup semantics) instead of throwing.

```python
if worktree_exists(...):       # check git worktree list
    git_worktree_remove(...)   # clean the stale one
git_worktree_add(...)          # create fresh
```

## Step 3 — Later hardening

PR #48 (MNT-105 era) hardened the logic further for different worktree reference types (branch references vs. raw paths), so the same recovery applies regardless of how the stale entry was recorded.

## Test Results

Tests cover the existing-worktree scenario: a run against a path that already has a worktree now succeeds by cleaning up and recreating.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-47
