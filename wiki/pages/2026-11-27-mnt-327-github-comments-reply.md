---
title: 'MNT-327: GitHub comments reply'
generated: {by: demetra, at: '2026-11-27T00:00:00Z'}
description: Implemented a GitHub comment reaction service using the GitHub CLI to post "eyes" reactions on merge/rebase/fix review comments, integrated with the listener daemon's notification processing flow, and added comprehensive tests for various scenarios.
type: implementation
status: stable
session_id: ses_de2abeac8ffeI4W1WbzAa4Q2k0
services: [listener.py, daemons/listener, vcs/__init__, vcs/github, pyproject, test_github, test_listener, uv, INDEX, 2026-11-27-mnt-327-github-comments-reply]
branch: mnt-327-github-comments-reply
tickets: [MNT-327]
tags: [wiki, feature, infrastructure]
related: [2026-11-26-mnt-324-comments-listener.md, 2026-09-14-listener-readline-limit-crash.md]
---

# MNT-327: GitHub comments reply

## TL;DR

Implemented GitHub comment reactions to acknowledge when a session is picked up from a merge/rebase/fix review comment. Added a new `react_to_comment` service that posts an "eyes" reaction using the GitHub CLI, called from `process_notification` in the listener daemon. The reaction happens immediately when the workflow is enqueued, not waiting for worker execution.

## Overview

The implementation adds a new GitHub CLI-based reaction service and integrates it with the existing notification processing flow. Key aspects:

- Reacts only to merge/rebase/fix review comments (not CodeRabbit comments)
- Uses the issues/comments endpoint (not pull request review comments)
- Fires at notification pickup time in the listener daemon
- Gracefully handles failures with warning logs

## Step 1 — Add comment reaction service

**File:** demetra/services/vcs/github.py:449-501

Added the core `react_to_comment` function that uses GitHub CLI to post reactions:

```python
async def react_to_comment(
    comment_id: str,
    full_name: str,
    target_path: Path,
    environment: SessionEnvironment | None = None,
    project_id: str | None = None,
) -> bool:
    command = [
        str(GITHUB["path"]),
        "api",
        "--method",
        "POST",
        "-f",
        "content=eyes",
        f"repos/{full_name}/issues/comments/{comment_id}/reactions",
    ]
    # ... error handling and validation ...
```

Validates inputs with regex patterns for comment IDs and repository names.

## Step 2 — Integrate with notification processing

**File:** demetra/services/daemons/listener.py:422-430

Added reaction call in `process_notification` before workflow enqueue:

```python
try:
    await react_to_comment(
        comment_id=pr_info.get("comment_id", ""),
        full_name=full_name,
        target_path=BASE_PATH,
    )
except (OSError, RuntimeError) as e:
    logger.warning(f"Failed to react to the triggering comment for PR #{pr_number}: {e}")
```

## Step 3 — Pass comment ID through webhook handlers

**File:** demetra/listener.py:60

Ensured comment ID is propagated from webhook payload to PR info:

```python
pr_info["comment_id"] = comment["id"]
```

## Test Results

All 1923 existing tests passed. New tests were added for the reaction service covering:

- Successful reaction posting
- Invalid input handling
- CLI failure scenarios
- Endpoint construction

## Follow-ups

- None

## References
- External: https://linear.app/mnt/issue/MNT-327/github-comments-reply
- Related: [2026-11-26-mnt-324-comments-listener](/pages/2026-11-26-mnt-324-comments-listener.md)
- Related: [2026-09-14-listener-readline-limit-crash](/pages/2026-09-14-listener-readline-limit-crash.md)

> **Consistency note (2026-11-27, Consistency Agent):** Step 3 cites `demetra/listener.py:60` (`pr_info["comment_id"] = comment["id"]`), which is the GitHub **notifications polling daemon** (`fetch_subject_comment`), not a webhook handler. Webhook `issue_comment` events are handled separately in `demetra/services/vcs/github.py:609-640` (`webhook_rebase_handler`), which also extracts `comment_id` from `payload["comment"]` and calls `react_to_comment` before enqueueing merge/rebase.
