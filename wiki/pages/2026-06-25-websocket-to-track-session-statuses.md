---
title: Websocket to track session statuses
date: 2026-06-25
type: implementation
status: resolved
session_id: -
services: [api, react, workflows]
branch: -
tickets: [MNT-101]
tags: [websocket, json, status, react]
related: []
---

# Websocket to track session statuses

## TL;DR

Rebuilt the session-log websocket from raw text frames to typed JSON so the React app can distinguish live log lines from status changes. The websocket now sends `{"type": "log", ...}` and `{"type": "status", ...}` messages; the frontend appends log text and re-renders the session name/status block accordingly. Status updates are emitted only when the step or name actually changes, and viewers keep tailing recent history.

---

## Overview

The old websocket streamed raw text, so the frontend could not tell a log line from a session-status transition. The rebuild introduces a typed message envelope.

## Step 1 — Emit typed JSON from the websocket

**File:** `api` websocket endpoint

Messages now carry two fields:

```json
{"type": "log", "data": {"text": "..."}}
{"type": "status", "data": {"name": "...", "status": "..."}}
```

`type` is one of `log` or `status`; `data` holds the payload.

## Step 2 — Parse on the frontend

**File:** `react` session log viewer

The websocket client parses each JSON frame:

- `log` → append `data.text` to the session log
- `status` → update the session name / status text and its styling

## Step 3 — Emit status changes from the workflow

**File:** `workflows`

The workflow sends a status message whenever the session status changes in the DB. Status updates are deduplicated — emitted only when the step or name actually changes. Log viewers also load recent history and keep tailing for new frames.

## Test Results

Tests for the websocket message shape and for the sidebar/session rendering on both `log` and `status` frames.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-101 — Websocket to track session statuses (Linear)](https://linear.app/mnt/issue/MNT-101)
