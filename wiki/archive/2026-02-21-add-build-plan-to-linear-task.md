---
title: Add a build plan to linear task
generated: {by: demetra, at: '2026-02-21T00:00:00Z'}
description: Records MNT-29 adding an async Linear `post_comment` service that posts the extracted build plan to the ticket right after the plan step, with tests; a later `posted_to_linear` flag from MNT-39 prevented double-posting when plans are reused, and the page was archived.
type: implementation
status: deprecated
session_id: '-'
services: [linear, workflows]
branch: '-'
tickets: [MNT-29]
tags: [linear, comment, build-plan]
related: []
---

# Add a build plan to linear task

> **Archived on 2026-08-18.** Useful info merged into
> [2026-07-16-fix-empty-build-plan-loop](/archive/2026-07-16-fix-empty-build-plan-loop.md). See wiki/archive/ for the
> original.

## TL;DR

When the plan agent finishes, the extracted build plan is posted to the Linear ticket as a comment. A new async Linear service posts the comment (input: linear task id + comment text) and the workflow calls it right after the plan step produces a plan. Tests cover the new service.

---

## Overview

MNT-29 surfaces the plan where stakeholders can see it: directly on the Linear ticket, automatically, the moment planning completes.

## Step 1 — Add the post-comment service

**File:** `demetra/services/linear.py`

```python
async def post_comment(ticket_id: str, comment_text: str, ...) -> None:
    # GraphQL commentCreate on the ticket
```

The service is async (consistent with the Linear API client) and takes exactly the linear task id and the comment text.

## Step 2 — Wire into the workflow after the plan step

**File:** `main.py`

Once the plan step produces a plan, the workflow calls the service with the ticket id and the cleaned plan text. This is the same cleaned plan produced by `extract_plan` (MNT-20).

## Step 3 — Avoid double-posting

Later, MNT-39's `posted_to_linear` flag on the `sessions` table prevents the plan from being posted twice when the plan is reused from the database.

## Test Results

Tests were added for the new Linear post-comment service (ticket-id + text inputs, comment posted).

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-29
