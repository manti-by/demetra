---
title: Add context compaction
date: 2026-07-07
type: implementation
status: resolved
session_id: "-"
services: [opencode, database, workflows, settings]
branch: "-"
tickets: [MNT-122]
tags: [context, compaction, session-history, tokens]
related:
- 2026-07-23-session-tokens-audit-revalidation.md
- 2026-07-23-session-history-modal.md
---

# Add context compaction

## TL;DR

Added automatic context-length tracking and compaction for OpenCode sessions. `session_history` records length after each step; when it exceeds `CONTEXT_COMPACTION_THRESHOLD` (default 100_000) the session is compacted via `/compact`. Later disabled in MNT-145 due to cumulative `length` (see [[2026-07-23-session-tokens-audit-revalidation]]), then re-enabled.

---

## Overview

Long sessions drift past usable context windows, degrading plan/build quality. This tracks length after every step and compacts over threshold.

> **Update (2026-08-04):** MNT-145 disable was reversed — `5f8e428` commented out the `build.py` caller, `47d428d` (2026-07-23) re-enabled it via non-cumulative `context_tokens`. Compaction is live (`demetra/workflows/build.py:100`). See [[2026-07-23-session-tokens-audit-revalidation]].

## Changes

- **Session history** (`session_history` table + `SessionHistory` dataclass): many-to-one via `session_id`, columns `id/session_id/step/length/created_at`, migration `add_session_history_table`, services `record_session_history`/`get_session_history`.
- **Measurement + compaction** (opencode helpers): `get_opencode_session_length` (parses `opencode export` tokens), `opencode_compact_session` (`opencode run --session <id> --dir <target> /compact`).
- **Threshold** (`settings`): `CONTEXT_COMPACTION_THRESHOLD`, default 100_000 tokens.
- **Workflow**: `check_and_compact_context` records history after each step and triggers compaction over threshold.

## Test Results

Tests for history recording, length measurement, and compaction triggering.

## Known follow-up

Compaction disabled in MNT-145 (cumulative `length`) — see [[2026-07-23-session-tokens-audit-revalidation]]; re-enabled as above.

---

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-23-session-tokens-audit-revalidation]] · [[2026-07-23-session-history-modal]]
- External: [MNT-122 — Add context compaction (Linear)](https://linear.app/mnt/issue/MNT-122)
