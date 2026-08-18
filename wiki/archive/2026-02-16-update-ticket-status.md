---
title: Update ticket status
date: 2026-02-16
type: implementation
status: resolved
session_id: -
services: [linear, workflows]
branch: -
tickets: [MNT-23]
tags: [linear, status, workflow]
related: []
---

# Update ticket status

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-08-05-pr-creation-failure-handler]]. See wiki/archive/ for the
> original.

## TL;DR

Linear services now update a ticket's status at workflow milestones: `update_ticket_status` plus `get_ticket_states` in the Linear integration, called from `main.py` to set `In Progress` before the plan agent and `In Review` after pushing to GitHub. Errors fall back gracefully. Version bumped to 1.2.2.

---

## Overview

MNT-23 gives the supervisor control over Linear ticket state so the ticket lifecycle tracks the workflow: started → in progress → in review.

## Step 1 — Add Linear status services

**File:** `demetra/services/linear.py`

```python
def get_ticket_states(...) -> list:      # fetch available states for the team
def update_ticket_status(ticket_id, state, ...) -> None:   # GraphQL mutation
```

`update_ticket_status` is implemented as a GraphQL mutation; `get_ticket_states` supplies the valid state names to pass into it.

## Step 2 — Wire status updates into `main.py`

**File:** `main.py`

- Before the plan agent runs → ticket moved to `In Progress`.
- After pushing to GitHub → ticket moved to `In Review`.

## Step 3 — Graceful error handling

Status updates are wrapped so a Linear API failure does not abort the whole workflow — the run continues and the failure is surfaced rather than raised.

## Test Results

Verified through workflow runs; status transitions were observed in Linear. The README workflow diagram was updated to reflect the new transitions.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-23
