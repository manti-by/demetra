---
title: Stream logs on frontend
date: 2026-03-05
type: implementation
status: resolved
session_id: -
services: [api, watcher]
branch: -
tickets: [MNT-53]
tags: [websocket, logs, streaming]
related: []
---

# Stream logs on frontend

## TL;DR

Added a FastAPI websocket endpoint that tails the watcher session log and streams lines to the frontend in real time, with graceful handling of connection errors. This is the precursor to the typed JSON websocket in MNT-101 and the per-session log isolation in MNT-54.

---

## Overview

The first live-view path for watcher output: instead of polling files, the frontend subscribes to a websocket that pushes new log lines as they are written.

- FastAPI websocket endpoint tailing the watcher session log
- Streams log lines to connected clients
- Graceful handling of connection errors
- Tests for the websocket

## Step 1 — Websocket endpoint

**File:** `demetra/api.py`

Added a websocket route that tails the watcher session log and forwards each new line to the connected client, so the frontend can render logs live.

## Step 2 — Connection error handling

Wrapped the streaming loop so connection errors are handled gracefully — a dropped client does not crash the endpoint or the watcher.

## Test Results

Tests were added for the websocket endpoint.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-53
