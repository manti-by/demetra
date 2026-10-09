---
title: 'MNT-219: Session log autoscroll'
date: '2026-09-24'
type: implementation
status: resolved
session_id: ses_f2d26be6effeaTlsjxXevDtWSJ
services: [react]
branch: mnt-219-session-log-autoscroll
tickets: [MNT-219]
tags: [wiki, frontend, feature]
related: [2026-06-25-websocket-to-track-session-statuses.md]
---
# MNT-219: Session log autoscroll

## TL;DR

The session log autoscroll feature was implemented, allowing the log to automatically scroll to the latest records when new logs are received or when the session is changed. The update was successfully tested and documented in a new wiki page. The React frontend was modified to achieve this functionality.

---

## Overview

The implementation involved updating the `LogConsole.tsx` file to scroll to the bottom of the session log when a new log record is received or when the session is changed. The `App.css` file was also modified to turn off CSS smooth scroll on `.log-content`. Additionally, new tests were added to `LogConsole.test.tsx` to cover the scrolling behavior.

## Build plan

## Implementation Plan
### Approach
The plan involves updating the `LogConsole.tsx` file to scroll to the bottom of the session log when a new log record is received or when the session is changed. This will be achieved by modifying the existing `useEffect` hook to depend on both `taskId` and `logs`, and changing the `scrollIntoView` call to `{ block: "end" }`. Additionally, the CSS smooth scroll will be turned off on `.log-content` to prevent the browser from fighting the imperative scroll.

### Build Steps

1. **Edit `react/src/components/LogConsole.tsx`**: Update the `useEffect` hook to depend on `taskId` and `logs`, and change the `scrollIntoView` call to `{ block: "end" }`.
```tsx
useEffect(() => {
  if (logsEndRef.current && typeof logsEndRef.current.scrollIntoView === 'function') {
…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f2d26be6effeaTlsjxXevDtWSJ`

---

## Follow-ups

- None

## References

- Related: [[2026-06-25-websocket-to-track-session-statuses]]
- External: https://linear.app/mnt/issue/MNT-219/session-log-autoscroll

> **Consistency fix (2026-09-28, Consistency Agent):** mirrored `related:` into the body; trimmed the ~150-entry `services:` filename dump to subsystem tags. The `Changed files`/`Stat` sections below are a whole-tree diff against a stale base, not this ticket's changeset — e.g. they show `demetra/services/linear/config.py` / `llm/config.py` as added (both deleted by MNT-205 in `68e53b7` and absent from HEAD), `configs/services/*.service` + `configs/bootstrap.sh` (no `configs/services/` dir on HEAD), and the `.opencode/skills/wiki-sync => wiki-update` rename (never landed; only `wiki-sync` exists). The ticket's real changeset is `LogConsole.tsx` + `App.css` + `LogConsole.test.tsx` per the Overview.
