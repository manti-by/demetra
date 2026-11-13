---
title: 'CH-11: Failed status for Awaiting Input tickets'
date: '2026-11-13'
type: implementation
status: resolved
session_id: ses_e2c7d823cffeeyVpystxIHvf9u
services: [library, queries, daemons/watcher, linear/__init__, linear/states, workflows, main, pyproject, conftest, test_entrypoints, test_failure, test_linear, test_more_coverage, test_workflows, uv, .sessions, INDEX, 2026-11-12-ch-11-failed-status-for-awaiting-input-tickets]
branch: ch-11-failed-status-for-awaiting-input-tickets
tickets: [CH-11]
tags: [wiki, bug, backend]
related: [2026-07-21-awaiting-input-status-for-session.md, 2026-08-28-awaiting-input-workflow-continues-to-review.md, 2026-08-05-pr-creation-failure-handler.md]
---

# CH-11: Failed status for Awaiting Input tickets

## TL;DR

This session implemented the correct status transition for tickets needing input, moving them to "Awaiting Input" instead of "Failed". The solution involved creating a new Linear state resolution service, updating the notification workflow, and adding proper error handling for cases where the transition can't be completed.

## Overview

The system needed to properly handle tickets requiring user input by moving them to an "Awaiting Input" state rather than marking them as failed. This required:

1. Adding state resolution capabilities to query and validate Linear workflow states
2. Updating the notification system to handle the new transition
3. Implementing proper error handling for failed transitions

## Step 1 — State resolution service

**File:** demetra/services/linear/states.py

Added a new service module to handle Linear state resolution:

```python
class LinearState:
    """Dataclass representing a Linear workflow state."""

async def resolve_state_id(
    name: str, configured_id: str | None, team_id: str | None
) -> tuple[str | None, str | None]:
    """Resolve a state id by name or configured id, with validation."""
```

**File:** demetra/queries/get_team_states.gql

Added GraphQL query to fetch team states:

```graphql
query GetTeamStates($teamId: String!) {
  team(id: $teamId) {
    states {
      nodes {
        id
        name
        type
      }
    }
  }
}
```

## Step 2 — Notification workflow update

**File:** demetra/workflows/notifications.py

Updated notification system to use the new state resolution:

```python
async def notify_status(
    ticket_id: str,
    status: str,
    user_id: str | None = None,
    project_id: str | None = None,
) -> bool:
    """Notify status change with proper state resolution."""
```

## Step 3 — Error handling

**File:** demetra/library/exceptions.py

Added new exception type for failed transitions:

```python
class AwaitingInputError(DemetraError):
    """The task could not be parked in Awaiting Input, so the run must fail
    without moving the ticket: bouncing it back to TODO would re-queue it into
    the build path with the questions still unanswered.
    """
```

## Test Results

The implementation includes comprehensive test coverage:

- State resolution service tests
- Notification workflow tests
- Error handling scenarios
- Integration tests for the complete flow

## Follow-ups

- None

## References

- External: <linear ticket URL>
- Related: [[2026-07-21-awaiting-input-status-for-session]]
- Related: [[2026-08-28-awaiting-input-workflow-continues-to-review]]
- Related: [[2026-08-05-pr-creation-failure-handler]]
