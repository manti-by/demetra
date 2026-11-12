---
title: 'CH-12: Session list order'
date: '2026-11-12'
type: implementation
status: resolved
session_id: ses_e2ef57585ffeVMuauaIDrGcws1
services: [api, persistence/database, persistence/queue, pyproject, App, App.test, SessionList.test, SessionList, SessionSidebar.test, StyleGuide, api.test, test_queue, test_session_logging, uv, .sessions, INDEX, 2026-11-12-ch-12-session-list-order]
branch: ch-12-session-list-order
tickets: [CH-12]
tags: [wiki, feature, frontend, backend]
related: [2026-11-04-chat-session-list-and-rerun.md, 2026-10-12-session-state-flow-feedback-loops.md]
---

# CH-12: Session list order

## TL;DR

Implemented session list ordering improvements to show active sessions (not completed/researched) at the top with a visual separator. Added live session status tracking via Redis/RQ integration and blinking indicators on the frontend. The changes include a new API endpoint for live session detection and React component updates for the visual presentation.

## Overview

The implementation focused on three main areas:
1. Backend service to identify live sessions via RQ job registry
2. API endpoint to expose live session status to frontend
3. Frontend UI changes for grouping and visual indicators

## Step 1 — Live session detection service

**File:** demetra/services/persistence/queue.py

Added Redis/RQ integration to track currently running sessions:

```python
def get_live_task_ids() -> list[str]:
    """Return the task ids of the workflow jobs that are currently running.
    
    A job is live while its execution sits in the queue's started-job registry,
    which RQ fills right before execution and empties on completion.
    """
    registry = StartedJobRegistry('default', connection=Redis.from_url(REDIS_URL))
    return [job.id for job in registry.get_job_ids()]
```

## Step 2 — Live sessions API endpoint

**File:** demetra/api/sessions.py

Added new endpoint that intersects live jobs with user-owned sessions:

```python
@router.get("/live")
async def list_live_sessions(user: UserResponse = Depends(get_current_user_dep)) -> list[str]:
    """List the sessions whose workflow job is currently running."""
    live_task_ids = await asyncio.to_thread(get_live_task_ids)
    owned_task_ids = await get_user_session_task_ids(user_id=user.id, task_ids=live_task_ids)
    return [task_id for task_id in live_task_ids if task_id in owned_task_ids]
```

## Step 3 — Session ownership verification

**File:** demetra/services/persistence/database.py

Added helper to verify session ownership without full table scan:

```python
async def get_user_session_task_ids(user_id: str, task_ids: list[str]) -> set[str]:
    """Return which of the given task ids are sessions owned by a user."""
    async with get_connection() as connection:
        result = await connection.execute(
            select(sessions.c.task_id).where(
                sessions.c.user_id == user_id,
                sessions.c.task_id.in_(task_ids),
            )
        )
    return {row.task_id for row in result}
```

## Step 4 — Frontend session grouping

**File:** react/src/components/SessionList.tsx

Updated React component to:
- Split sessions into active/completed groups
- Add horizontal rule separator
- Implement blinking indicators for live sessions
- Preserve created_at DESC ordering within groups

## Test Results

All 1345 tests passed successfully. Key test coverage includes:
- Redis/RQ integration tests for live session detection
- API endpoint tests for auth and data scoping
- Frontend component tests for visual presentation
- Graceful degradation tests for Redis failures

## Follow-ups

- None

## References
- External: <linear ticket URL>
- Related: [[2026-11-04-chat-session-list-and-rerun]]
- Related: [[2026-10-12-session-state-flow-feedback-loops]]
