---
title: 'MNT-324: Comments listener'
generated: {by: demetra, at: '2026-11-26T00:00:00Z'}
description: The CodeRabbit comments listener subsystem was implemented to extract, store, and process CodeRabbit comments from GitHub review threads using Redis and a single workflow, with all 1861 tests passing successfully.
type: implementation
status: stable
session_id: ses_de8913e08ffe4MCth0tdU6a5bi
services: [.env.docker, library, listener.py, comments, daemons/listener, persistence/queue, vcs/github, settings, workflows, pyproject, test_comments_workflow, test_github, test_listener, test_queue, uv, INDEX, 2026-11-26-mnt-324-comments-listener]
branch: mnt-324-comments-listener
tickets: [MNT-324]
tags: [wiki, feature, backend]
related: []
---

# MNT-324: Comments listener

## TL;DR

This session implemented a CodeRabbit comments listener that extracts CodeRabbit comments from GitHub review threads, stores them in Redis, and runs a single workflow to process them. The implementation includes new services for comment resolution and Redis batch storage, along with extensive testing.

## Overview

The implementation adds a CodeRabbit comments listener that:
1. Identifies CodeRabbit comments by author login (`coderabbitai[bot]` or `coderabbitai`)
2. Extracts unresolved review threads containing CodeRabbit comments
3. Stores pending comments in Redis with a TTL
4. Runs a single workflow to process all pending comments
5. Resolves the comments after pushing fixes to GitHub

## Step 1 — Add configuration and constants

**File:** demetra/library/constants.py:14
```python
CODERABBIT_AUTHOR_LOGINS: tuple[str, ...] = ("coderabbitai[bot]", "coderabbitai")
```

**File:** .env.docker.example:72
```python
# A batch of CodeRabbit comments saved to Redis stays claimable for this long
# (seconds). The listener does not enqueue a second workflow while a batch is
# pending, and the comments workflow clears the key after it pushes the fixes.
# PENDING_COMMENTS_TTL=86400
```

## Step 2 — Extend GitHub service

Added methods to:
- Fetch unresolved review threads with IDs
- Filter threads by CodeRabbit author login
- Resolve threads via GraphQL mutation

## Step 3 — Add Redis batch storage

Implemented Redis operations for:
- Saving pending comments
- Loading pending comments
- Clearing pending comments

## Step 4 — Create comments resolver service

**File:** demetra/services/comments.py:14
```python
async def resolve_pending_comments(
    task_id: str,
    target_path: Path,
    environment: SessionEnvironment | None = None,
    project_id: str | None = None,
) -> bool:
    """Resolve the saved CodeRabbit threads after their fixes were pushed.
    """
```

The resolver:
1. Loads pending comments from Redis
2. Extracts unique thread IDs
3. Resolves threads via GitHub API
4. Clears Redis on success

## Test Results

Added extensive test coverage across:
- GitHub service (`test_github.py`)
- Redis queue (`test_queue.py`) 
- Listener (`test_listener.py`)
- Comments workflow (`test_comments_workflow.py`)

All 1861 tests passed successfully.

## Follow-ups
- None

## References
- External: https://linear.app/mnt/issue/MNT-324/comments-listener
