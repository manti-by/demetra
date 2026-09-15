---
title: Add delete button for a session
date: 2026-06-02
type: implementation
status: resolved
session_id: "-"
services: [api, react, database]
branch: "-"
tickets: [MNT-86]
tags: [sessions, delete, api, react]
related: []
---

# Add delete button for a session

## TL;DR

Sessions can now be deleted entirely. A delete button sits near the clear button in the session log header; on click it sends a delete request to the API, which removes the session and all related objects (database records, log files). The session list auto-refreshes after deletion, and the button is styled with hover effects. Precursor attempts (#35 MNT-85, #33 MNT-82) were superseded by this PR (#38).

---

## Overview

Before this ticket a session could be cleared but not removed. A dedicated delete action gives users a way to drop a session and its artifacts completely.

- Delete button near the clear button in the session log header
- API deletes the session and all related objects (DB records, log files)
- Session list auto-refreshes after deletion
- Button styled with hover effects

## Step 1 — API delete endpoint

Added a delete endpoint that removes the session and every related object: the database record plus the session's log files on disk.

## Step 2 — Delete button in the UI

Added a delete button next to the existing clear button in the session log header, with hover styling to match the rest of the controls.

## Step 3 — Auto-refresh

After a successful delete, the session list refreshes automatically so the removed session disappears without a manual reload.

## Test Results

Tests were added for the API delete endpoint.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-86
