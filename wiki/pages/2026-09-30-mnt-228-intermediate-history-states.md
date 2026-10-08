---
title: 'MNT-228: Intermediate history states'
date: '2026-09-30'
type: implementation
status: resolved
session_id: 8a73875f-33bb-4c95-807d-570bbb05540b
services: [persistence, workflows, api, react]
branch: mnt-228-intermediate-history-states
tickets: [MNT-228]
tags: [wiki, feature, backend, frontend]
related: [2026-07-23-session-history-modal.md, 2026-08-25-mnt-181-total-tokens-counter.md, 2026-07-23-session-tokens-audit-revalidation.md]
---
# MNT-228: Intermediate history states

## TL;DR

Session history now captures intermediate step transitions across all workflow stages rather than only steps with token metrics. Passing session identifiers into step update operations enables automatic recording of timestamped history entries without requiring database schema changes. Additionally, the frontend history UI now displays localized clock times instead of relative dates.

---

## Overview

The database persistence layer (`demetra/services/persistence/database.py`) was updated to insert step-only rows into `session_history` when `update_session_step` receives a `session_id`. Workflow modules (`demetra/workflows/plan.py`, `build.py`, `lint.py`, `research.py`, and `cleanup.py`) were updated to pass `session_id` across intermediate transitions, fixing missing history for review and validation steps. In the frontend, `react/src/components/SessionHistory.tsx` was modified to format entries with localized clock times while retaining full timestamps in tooltip attributes.

## Build plan

Here is the summary of the implementation plan:

### Key Technical Decisions
- **Extend `update_session_step`**: Instead of adding ~15 duplicate `record_session_step_history` calls across workflows, add an optional `session_id` parameter directly to `update_session_step`. When provided, it inserts a `session_history` row (step + timestamp only) in the same transaction.
- **No Database Migration**: The token usage and `model` columns in `session_history` are already nullable, so step-only history rows can be inserted without schema changes.
- **Skip `session_id` on Terminal Steps**: In `cleanup.py`, `completed` and failure updates will omit `session_id` to prevent duplicate history rows, as `record_session_step_history` already writes token rows immediately following those steps.
- **Fronte…

## Test Results

- Session status: `resolved`
- OpenCode session id: `8a73875f-33bb-4c95-807d-570bbb05540b`

---

## Follow-ups

- None

## References

- Related: [[2026-07-23-session-history-modal]]
- Related: [[2026-08-25-mnt-181-total-tokens-counter]]
- Related: [[2026-07-23-session-tokens-audit-revalidation]]
- External: https://linear.app/mnt/issue/MNT-228/intermediate-history-states
