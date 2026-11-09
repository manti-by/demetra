---
title: 'MNT-277: Do not remove git worktree for sessions'
date: '2026-11-06'
type: implementation
status: resolved
session_id: ses_e4ea43174ffeYjDE3I2j0qhRvE
services: [library, workflows, settings, vcs]
branch: mnt-277-do-not-remove-git-worktree-for-sessions
tickets: [MNT-277]
tags: [wiki, feature, backend]
related: [2026-11-04-chat-session-list-and-rerun.md, 2026-08-19-build-agent-stale-session-deleted-worktree.md]
---

# MNT-277: Do not remove git worktree for sessions

## TL;DR

This session implemented a flag to preserve git worktrees for all session types (chat and Linear) when `GIT_DISABLE_WORKTREE_REMOVAL=true`. The flag is false by default, maintaining the existing behavior of removing worktrees after sessions complete. Tests were updated to verify the new behavior.

## Overview

The changes allow preserving git worktrees and branches for all session types when the `GIT_DISABLE_WORKTREE_REMOVAL` flag is enabled. This enables reruns to continue from the same code state. The policy was moved from the VCS service to the workflow layer for better encapsulation.

## Step 1 — Add disable_worktree_removal flag

**File:** demetra/library/types.py:66

```python
class GitConfig(PathConfig):
    disable_worktree_removal: bool
```

Added the `disable_worktree_removal` boolean field to `GitConfig` to control worktree removal behavior.

## Step 2 — Update git_cleanup signature and docs

**File:** demetra/services/vcs/git.py:488

```python
async def git_cleanup(context: Context, is_success: bool, remove_worktree: bool = True) -> bool:
```

Modified `git_cleanup` to accept a `remove_worktree` parameter defaulting to `True`. Updated the docstring to explain the new behavior.

## Step 3 — Add GIT_DISABLE_WORKTREE_REMOVAL env var

**File:** .env.docker.example:68

```env
# Git worktrees: chat sessions always keep their worktree and branch so a
# rerun continues the same code; set this to true to keep every worktree
# (Linear runs included) instead of removing it at the end of a run.
# GIT_DISABLE_WORKTREE_REMOVAL=false
```

Added documentation for the new environment variable in the example config.

## Step 4 — Update cleanup_workflow logic

**File:** demetra/workflows/cleanup.py:172

```python
remove_worktree = not (context.is_chat or GIT["disable_worktree_removal"])
```

Modified the cleanup workflow to skip worktree removal when either in chat mode or `GIT_DISABLE_WORKTREE_REMOVAL` is true.

## Test Results

All 1210 tests passed, including new test cases verifying the worktree preservation behavior:

- `test_cleanup_workflow_keeps_worktree_when_removal_disabled`
- `test_git_cleanup_keeps_worktree_and_branch_when_removal_disabled`

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-277/do-not-remove-git-worktree-for-sessions
- Related: [[2026-11-04-chat-session-list-and-rerun]]
- Related: [[2026-08-19-build-agent-stale-session-deleted-worktree]]
