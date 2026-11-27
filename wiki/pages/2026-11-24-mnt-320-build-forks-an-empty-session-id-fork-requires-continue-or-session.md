---
title: 'MNT-320: Build forks an empty session id — "--fork requires --continue or --session"'
generated: {by: demetra, at: '2026-11-24T00:00:00Z'}
description: MNT-320 fixed builds forking an empty session id, which the OpenCode CLI rejected with "--fork requires --continue or --session" — empty ids are now normalised to NULL across the model, workflow, agent and database layers, with a migration backfilling existing rows.
type: implementation
status: stable
session_id: ses_df4e93215ffeb0Mmg5dv05kCwc
services: [library, agents/opencode, persistence/database, workflows, b0c1d2e3f4a5_normalize_empty_session_ids, pyproject, conftest, test_database, test_migrations, test_models, test_opencode, test_workflows, uv]
branch: mnt-320-build-forks-an-empty-session-id-fork-requires-continue-or-session
tickets: [MNT-320]
tags: [wiki, backend, bug]
related: [2026-10-16-mnt-234-isolate-session-context.md, 2026-10-16-mnt-251-session-attribution-accounting.md]
---

# MNT-320: Build forks an empty session id — "--fork requires --continue or --session"

## TL;DR

Fixed a workflow failure where builds would fork an empty session ID, causing the OpenCode CLI to reject the command. The root cause was layered: empty session IDs were being treated as valid when they should be normalized to NULL. Implemented fixes across model, workflow, agent, and database layers to ensure consistent handling of empty session IDs.

## Overview

The changes normalize empty session IDs to NULL at every layer, ensuring `--fork` is only used with valid session IDs. This involved:

1. Model layer changes to treat empty IDs as absent
2. Workflow changes to check for truthy session IDs
3. Agent layer hardening to handle malformed session data
4. Database migration to normalize existing empty IDs

## Step 1 — Model Layer Changes

**File:** demetra/library/models.py:867-874

Modified `Context.session_id` to return `None` for empty session IDs and updated docstrings to document this behavior:

```python
if self.session is None:
    return None
return self.session.session_id or None
```

## Step 2 — Workflow Changes

**File:** demetra/workflows/build.py:130

Changed the fork condition to use truthiness check:

```python
fork = is_first_build and bool(context.session_id)
```

## Step 3 — Agent Layer Changes

**File:** demetra/services/agents/opencode.py

Multiple changes:
- Added input validation for session_id parameter
- Improved error handling for malformed session list output
- Modified session resolution logic:

```python
session_id = session_id or None
if continued_session_id:
    # Only emit --session/--fork for truthy IDs
```

## Step 4 — Database Layer Changes

**File:** demetra/services/persistence/database.py

Updated writers to store NULL instead of empty strings:

```python
"session_id": session_id or None
```

Added migration to normalize existing empty IDs:

```python
op.execute(sa.text("UPDATE sessions SET session_id = NULL WHERE session_id = ''"))
```

## Test Results

All 1570 tests passed, including new tests covering:
- Build step behavior with empty session IDs
- Database session ID normalization
- Model layer behavior
- Migration correctness
- Agent error handling

## Follow-ups
- None

## References
- External: https://linear.app/mnt/issue/MNT-320/build-forks-an-empty-session-id-fork-requires-continue-or-session
- Related: [2026-10-16-mnt-234-isolate-session-context](/pages/2026-10-16-mnt-234-isolate-session-context.md)
- Related: [2026-10-16-mnt-251-session-attribution-accounting](/pages/2026-10-16-mnt-251-session-attribution-accounting.md)
