---
title: 'CH-15: Worktree management'
generated: {by: demetra, at: '2026-11-19T00:00:00Z'}
description: CH-15 replaced the chat-only GIT_DISABLE_WORKTREE_REMOVAL switch with one WORKTREE_CLEANUP feature flag for chat and Linear sessions alike — enabled drops the worktree, pulls master and starts fresh, research always pulls master, and setup otherwise reuses the existing path.
type: implementation
status: stable
session_id: ses_df59e4802ffeUhHtbo2EE5qpr2
services: [.env.docker, .pre-commit-config, AGENTS, Dockerfile, Makefile, library, agents/opencode, runtime/subprocess, runtime/utils, vcs/__init__, vcs/git, settings, workflows, docker-compose.test, docker-compose, pyproject, ChatPanel, SessionList, NewChatPage, test_chats, test_docker_compose, test_opencode, test_session_environment, test_settings, test_subprocess, test_workflows, uv, .sessions, INDEX, 2026-11-04-chat-session-list-and-rerun, 2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions, 2026-11-17-langsmith-403-multipart-ingest, 2026-11-18-ch-14-langsmitherror, 2026-11-19-ch-15-worktree-management, 2026-11-23-docker-image-size-optimization]
branch: ch-15-worktree-management
tickets: [CH-15]
tags: [wiki, feature, backend]
related: [2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions.md, 2026-11-04-chat-session-list-and-rerun.md]
---

# CH-15: Worktree management

## TL;DR

This session implemented a new `WORKTREE_CLEANUP` feature flag to control worktree management behavior across both chat and Linear sessions. The flag replaces the previous chat-specific `GIT_DISABLE_WORKTREE_REMOVAL` setting with a more generic approach. When enabled, it forces fresh worktrees by dropping existing ones and pulling master before each session. The changes were verified through extensive testing and code review.

## Overview

The implementation consolidates worktree management behavior across session types while maintaining backward compatibility. Key changes include:

1. Adding a new `WORKTREE_CLEANUP` feature flag
2. Removing deprecated `GIT_DISABLE_WORKTREE_REMOVAL` configuration
3. Updating worktree creation and cleanup logic to respect the new flag
4. Ensuring research tasks always pull master regardless of flag state

## Step 1 — Add WORKTREE_CLEANUP flag

**File:** demetra/settings.py:66

```python
FEATURES: dict = {
    "is_ruff_enabled": env_get_bool("IS_RUFF_ENABLED", False),
    "is_pytest_enabled": env_get_bool("IS_PYTEST_ENABLED", False),
    "is_worktree_cleanup_enabled": env_get_bool("WORKTREE_CLEANUP", False),
}
```

The new boolean flag defaults to `False`, preserving existing behavior where worktrees are kept between sessions.

## Step 2 — Remove deprecated configuration

**File:** demetra/settings.py:195

```python
GIT: GitConfig = {
    "path": env_get_path("GIT_PATH", Path("/usr/bin/git")),
    "worktree_path": env_get_path("GIT_WORKTREE_PATH", HOME_PATH / ".demetra/worktrees/"),
}
```

The `disable_worktree_removal` setting was removed from `GitConfig` as it's superseded by the new feature flag.

## Step 3 — Update cleanup workflow

**File:** demetra/workflows/cleanup.py:216

```python
remove_worktree = FEATURES["is_worktree_cleanup_enabled"]
```

The cleanup workflow now determines whether to remove worktrees based solely on the new flag, removing the chat-specific exception.

## Step 4 — Enhance setup workflow

**File:** demetra/workflows/setup.py:26

```python
from demetra.services.vcs.git import (
    get_worktree_path,
    git_pull,
    git_worktree_create,
    git_worktree_drop,
    git_worktree_exists,
    git_worktree_has_operation,
)
```

The setup workflow was updated to check for existing worktrees and handle cleanup when the flag is enabled, ensuring fresh worktrees are created when requested.

## Test Results

All tests passed successfully:
- 1563 tests executed
- Ruff, type checking, and Bandit checks clean
- Pre-commit hooks passed
- Targeted workflow tests verified behavior

The implementation was verified through:
1. Code review confirming no remaining references to removed symbols
2. Testing workflow setup/cleanup behavior
3. Validation of feature flag integration

## Follow-ups

- None

## References

- External: -
- Related: [2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions](/pages/2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions.md)
- Related: [2026-11-04-chat-session-list-and-rerun](/pages/2026-11-04-chat-session-list-and-rerun.md)
