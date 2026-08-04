---
title: Add context compaction
date: 2026-07-07
type: implementation
status: resolved
session_id: -
services: [opencode, database, workflows, settings]
branch: -
tickets: [MNT-122]
tags: [context, compaction, session-history, tokens]
related: [2026-07-23-session-tokens-audit-revalidation.md, 2026-07-23-session-history-modal.md]
---

# Add context compaction

## TL;DR

Added automatic context-length checks and compaction for OpenCode agent sessions. A new `session_history` table records the context length after each workflow step, and when the recorded length exceeds `CONTEXT_COMPACTION_THRESHOLD` (default 100_000 tokens) the agent session is compacted via `/compact`. Compaction was later disabled in MNT-145 because the recorded `length` was cumulative, not per-message — see [[2026-07-23-session-tokens-audit-revalidation]] and [[2026-07-23-session-history-modal]].

---

## Overview

Long agent sessions drift past usable context windows, degrading plan/build quality. This change tracks session length after every build iteration and compacts when over the threshold.

## Step 1 — Persist session history

**File:** `session_history` table + `SessionHistory` dataclass

New table (many-to-one via `session_id`) with `id`, `session_id`, `step`, `length`, `created_at`, plus the `SessionHistory` dataclass. Migration `add_session_history_table` included. `record_session_history` and `get_session_history` services wrap it.

## Step 2 — Measure and compact OpenCode sessions

**File:** opencode helpers

- `get_opencode_session_length` — runs `opencode export` and parses the token counts.
- `opencode_compact_session` — runs `opencode run --session <id> --dir <target> /compact`.

## Step 3 — Threshold setting

**File:** `settings`

`CONTEXT_COMPACTION_THRESHOLD` setting, default 100_000 tokens.

## Step 4 — Workflow integration

**File:** `workflows`

`check_and_compact_context` records step history after each step and triggers compaction when the recorded length is over the threshold.

## Test Results

Tests across services, models, and workflows for history recording, length measurement, and compaction triggering.

## Known follow-up

Compaction was later disabled in MNT-145 because the recorded `length` was cumulative rather than per-message — see [[2026-07-23-session-tokens-audit-revalidation]].

---

## Follow-ups

None.

## References

- Related: [[2026-07-23-session-tokens-audit-revalidation]] · [[2026-07-23-session-history-modal]]
- External: [MNT-122 — Add context compaction (Linear)](https://linear.app/mnt/issue/MNT-122)
