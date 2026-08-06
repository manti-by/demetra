---
title: Websocket to track session statuses
date: 2026-06-25
type: implementation
status: resolved
session_id: -
services: [api, react, workflows]
branch: -
tickets: [MNT-101]
tags: [websocket, json, status, react, logs, streaming]
related: []
---

# Websocket to track session statuses

## TL;DR

Rebuilt the session-log websocket from raw text frames to typed JSON so the React app can distinguish live log lines from status changes. The websocket now sends `{"type": "log", ...}` and `{"type": "status", ...}` messages; the frontend appends log text and re-renders the session name/status block accordingly. Status updates are emitted only when the step or name actually changes, and viewers keep tailing recent history. This supersedes the original raw-text websocket from MNT-53 (`2026-03-05-stream-logs-websocket.md`), which first added FastAPI websocket log streaming to the frontend with graceful connection-error handling.

---

## Overview

The old websocket streamed raw text, so the frontend could not tell a log line from a session-status transition. The rebuild introduces a typed message envelope.

## Step 1 — Raw-text log streaming (MNT-53)

**File:** `demetra/api.py`

The first live-view path for watcher output: a FastAPI websocket endpoint tails the watcher session log and forwards each new line to the connected client, so the frontend can render logs live without polling files. The streaming loop handles connection errors gracefully — a dropped client does not crash the endpoint or the watcher. Tests covered the endpoint.

## Step 2 — Emit typed JSON from the websocket

**File:** `api` websocket endpoint

Messages now carry two fields:

```json
{"type": "log", "data": {"text": "..."}}
{"type": "status", "data": {"name": "...", "status": "..."}}
```

`type` is one of `log` or `status`; `data` holds the payload.

## Step 3 — Parse on the frontend

**File:** `react` session log viewer

The websocket client parses each JSON frame:

- `log` → append `data.text` to the session log
- `status` → update the session name / status text and its styling

## Step 4 — Emit status changes from the workflow

**File:** `workflows`

The workflow sends a status message whenever the session status changes in the DB. Status updates are deduplicated — emitted only when the step or name actually changes. Log viewers also load recent history and keep tailing for new frames.

## Test Results

Tests for the websocket message shape and for the sidebar/session rendering on both `log` and `status` frames.

---

## Follow-ups

None.

## References

- External: [MNT-101 — Websocket to track session statuses (Linear)](https://linear.app/mnt/issue/MNT-101), MNT-53
