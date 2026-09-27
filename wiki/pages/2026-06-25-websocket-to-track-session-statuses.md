---
title: Websocket to track session statuses
date: 2026-06-25
type: implementation
status: resolved
session_id: "-"
services: [api, react, workflows, sessions]
branch: "-"
tickets: [MNT-101, MNT-54]
tags: [websocket, json, status, react, logs, streaming, sessions, isolation]
related:
- 2026-07-16-fix-step-status-review-findings.md
- 2026-03-09-isolate-user-sessions.md
---
# Websocket to track session statuses

## TL;DR

Rebuilt the session-log websocket from raw text to typed JSON (`{"type":"log"}` / `{"type":"status"}`) so the React app distinguishes log lines from status transitions. Status messages are deduplicated (emitted only on actual change); viewers tail recent history. Supersedes the raw-text websocket from MNT-53 (`2026-03-05-stream-logs-websocket.md`).

---

## Overview

Raw-text streaming gave the frontend no way to tell a log line from a status transition. The rebuild introduces a typed envelope.

## Changes

- **Raw-text streaming (MNT-53)** (`demetra/api.py`): FastAPI websocket tails the session log and forwards lines; dropped clients don't crash the endpoint.
- **Typed JSON** (`api` websocket): messages are `{"type":"log","data":{"text":"..."}}` and `{"type":"status","data":{"name":"...","status":"..."}}`.
  > **Update (2026-08-27):** status payload key is now `step` not `status` — `{"type":"status","data":{"step":step,"name":name}}` (`demetra/api/watcher.py:30-38`), tracking the `status`→`step` column rename (e.g. [[2026-07-16-fix-step-status-review-findings]]). Envelope shape unchanged.
- **Frontend** (`react`): parses JSON — `log` appends text, `status` updates name/status styling.
- **Workflow** (`workflows`): emits status only when step or name actually changes; viewers load recent history and keep tailing.

## Test Results

Tests for message shape and sidebar/session rendering on both frame types.

---

## Source — [[2026-03-09-isolate-user-sessions]]

Per-session log files added in [[2026-03-09-isolate-user-sessions]] (MNT-54, 2026-03-09): each run writes to a temp file then renames to the task id under `LOG_PATH/sessions`. The MNT-101 websocket tails exactly this layout; dedup rule keeps `Session` updates minimal. Session ids are UUIDs.

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- External: [MNT-101 — Websocket to track session statuses (Linear)](https://linear.app/mnt/issue/MNT-101), MNT-53
