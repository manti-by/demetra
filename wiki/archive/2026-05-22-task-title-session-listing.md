---
title: Use task title for session listing
generated: {by: demetra, at: '2026-05-22T00:00:00Z'}
description: Records MNT-84, which made the sessions list show the task title (custom name with truncated-id fallback) instead of opaque ids, added a status-filterable sessions API (later renamed `step`), improved auth error messaging and reorganized routers under MNT-81; the page was later archived and merged into the total-tokens-counter page.
type: implementation
status: deprecated
session_id: '-'
services: [api, react]
branch: '-'
tickets: [MNT-84, MNT-59]
tags: [sessions, api, react, title, sidebar, websocket]
related: [2026-03-10-ui-for-sessions.md, 2026-07-16-fix-step-status-review-findings.md, 2026-08-25-mnt-181-total-tokens-counter.md]
---

# Use task title for session listing

> **Archived on 2026-10-26.** Useful info merged into
> [2026-08-25-mnt-181-total-tokens-counter](/pages/2026-08-25-mnt-181-total-tokens-counter.md). See wiki/archive/ for the original.

## TL;DR

The session list now shows the task title instead of the truncated session id. The sessions API gained an endpoint with optional status filtering, sessions display a custom name when available with a fallback to the truncated id, the React app renders the task title, and API auth error messaging was improved. Routers were reorganized as part of the MNT-81 refactor.

---

## Overview

Session ids are opaque and truncated, so the list was not useful for identifying work. Surfacing the task title (with a fallback) makes each row meaningful at a glance.

- Sessions API endpoint with optional status filtering
- Sessions display a custom name when available, falling back to the truncated id
- React app shows the task title
- API auth error messaging improved
- Routers reorganized (with MNT-81)

## Step 1 — Sessions API with status filter

Added an endpoint that lists sessions with optional status filtering, returning the session's custom name/task title for display.

## Step 2 — Name resolution

Session display logic uses a custom name when available and falls back to the truncated session id, so every row has a readable label.

## Step 3 — React app

The React session list renders the task title from the API instead of the session id.

## Step 4 — Auth error messaging

Improved the API auth error messages surfaced to the client during session requests.

## Test Results

Tests were updated for the new name field and status filtering.

---

## Source — [2026-03-10-ui-for-sessions](/archive/2026-03-10-ui-for-sessions.md)

Originally added in [2026-03-10-ui-for-sessions](/archive/2026-03-10-ui-for-sessions.md) on 2026-03-10 (MNT-59): the session
list UI came together here — a collapsible sidebar that minimizes to an icon, the
session list fed by `GET /api/v1/sessions` (including `pending` statuses from the
watcher/process-manager), and a `LogConsole` component that opens a websocket per
`task_id`. This is the layout MNT-84's title-based listing and the later
`SessionSidebar`/`LogConsole` components build on.

## Follow-ups

- None.

> **Consistency note (2026-08-24, Consistency Agent):** The sessions list filter was renamed from `status` to `step` during the step/status refactor — see [2026-07-16-fix-step-status-review-findings](/archive/2026-07-16-fix-step-status-review-findings.md). Current API: `GET /api/v1/sessions?step=...`.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- External: https://linear.app/mnt/issue/MNT-84
