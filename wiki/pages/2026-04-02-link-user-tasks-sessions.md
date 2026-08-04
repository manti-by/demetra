---
title: Link user, tasks and sessions
date: 2026-04-02
type: implementation
status: resolved
session_id: -
services: [database, linear, sessions]
branch: -
tickets: [MNT-63]
tags: [user-scoping, sessions, task-status, migration]
related: []
---

# Link user, tasks and sessions

## TL;DR

Scoped Demetra's data to the logged-in user: every retrieved task and session is linked to its user, and tasks are retrieved only for projects linked to that user. The `task_status` table was merged into `sessions` (status moved onto the session, the task-status table and its stale tests were removed), and `sessions` gained `project_id` and `user_id` columns with improved upserts and status lifecycle handling.

---

## Overview

Multi-user isolation was the driver: before this change, tasks/sessions were not attributed to the user who created them, and status lived in a separate `task_status` table. Both are now unified per session and scoped per user.

- Logged-in user linked to every retrieved task and session
- Tasks retrieved only for projects linked to a user
- `status` moved from `task_status` into `sessions`; task-status table + stale tests removed
- `project_id` and `user_id` columns added to `sessions`
- Improved upserts and status lifecycle handling
- Migration consolidates task-status into sessions

## Step 1 — User scoping

**File:** `demetra/services/database.py`, `demetra/services/linear.py`

Every retrieved task and session is now linked to the authenticated user. Linear task retrieval is filtered to projects linked to that user, so no user sees another user's tasks.

## Step 2 — Merge task-status into sessions

Moved `status` from the `task_status` table into `sessions`, removed the task-status table, and deleted the stale tests that referenced it.

## Step 3 — Schema and lifecycle

Added `project_id` and `user_id` columns to `sessions`, improved the upsert logic, and tightened the status lifecycle handling so status transitions are consistent. A migration consolidates task-status data into `sessions`.

## Test Results

Tests were updated and added for the user-scoped retrieval and merged status lifecycle.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-63
