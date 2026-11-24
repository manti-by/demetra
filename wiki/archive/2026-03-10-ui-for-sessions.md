---
title: UI for sessions
generated: {by: demetra, at: '2026-03-10T00:00:00Z'}
description: 'Records MNT-59, the first interactive sessions UI: a collapsible icon-only sidebar lists sessions from `/api/v1/sessions` (including statusless pending ones) and a LogConsole reconnects the websocket per selected `task_id` to stream that session''s log; the page was later archived and merged into the task-title session-listing page.'
type: implementation
status: deprecated
session_id: '-'
services: [react, api]
branch: '-'
tickets: [MNT-59]
tags: [react, sessions, sidebar, websocket]
related: []
---

# UI for sessions

> **Archived on 2026-08-18.** Useful info merged into
> [2026-05-22-task-title-session-listing](/archive/2026-05-22-task-title-session-listing.md). See wiki/archive/ for the
> original.

## TL;DR

Added a sessions UI to the React app: a collapsible left sidebar (minimized shows only icons), a session list loaded from `/api/v1/sessions` with statuses (including pending items with no explicit status), and a `LogConsole` that reconnects to the websocket for the selected session's task id to stream its log.

---

## Overview

First interactive view of workflow sessions: pick a session from the sidebar and watch its live log. This builds on the websocket streaming from MNT-53 and per-session logs from MNT-54.

- Collapsible left sidebar, minimized to icons
- Session list from `/api/v1/sessions` with statuses
- Pending sessions with no explicit status still shown
- `LogConsole` reconnects to the websocket for the selected `session.task_id`

## Step 1 — Collapsible sidebar

Added a left sidebar that collapses to icon-only mode to keep the workspace clean while preserving quick access.

## Step 2 — Session list

The sidebar lists sessions retrieved from `/api/v1/sessions`, each with its status. Filtering includes pending items that have no explicit status yet.

## Step 3 — Log console wiring

Selecting a session reconnects the `LogConsole` to the websocket for that session's `task_id`, so only the current session's log is streamed.

## Test Results

Tests cover the session list and sidebar components.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-59
