---
title: Isolate user sessions
date: 2026-03-09
type: implementation
status: resolved
session_id: -
services: [watcher, api, logging]
branch: -
tickets: [MNT-54]
tags: [logging, sessions, isolation]
related: []
---

# Isolate user sessions

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-25-websocket-to-track-session-statuses]]. See wiki/archive/ for the
> original.

## TL;DR

Replaced the single global watcher log with one log file per workflow session. If no ticket id is passed as a script argument, a temp log file with a random name is created and renamed to the Linear ticket id once the ticket is found; otherwise output appends to a log keyed by ticket id. Log files are centralized, append-only, never recreated, and the websocket now streams only the current session's log.

---

## Overview

Before this change every session wrote into one shared watcher log, so streams from different tickets were interleaved. Per-session log files give each workflow an isolated, resume-friendly trail and let the websocket scope output to the current session.

- One log file per workflow session (ticket-keyed, or temp name when no ticket id is passed)
- Temp file renamed to the Linear ticket id once the ticket is found
- Centralized session log directory; logs appended, never recreated
- Websocket streams only the current session's log
- Task id validated as a UUID on the websocket

## Step 1 — Per-session log files

**File:** `demetra/watcher.py`

When no ticket id is passed as a script argument, the session logs to a temp file with a random name. When a ticket id is present, output appends to a log file keyed by that ticket id.

## Step 2 — Rename on ticket resolution

Once the watcher resolves the Linear ticket for the session, the temp log file is renamed to the ticket id, so the trail is labeled by the actual task.

## Step 3 — Centralized, append-only logs

All session logs live in a centralized session log directory. Files are appended to across runs and never recreated, so a session's history survives restarts.

## Step 4 — Websocket isolation

The websocket endpoint now streams only the current session's log, and the task id passed to it is validated as a UUID.

## Test Results

Tests verify that different tickets get separate log files (no cross-ticket writes).

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-54
