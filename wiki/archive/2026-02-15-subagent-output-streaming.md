---
title: Subagent output streaming
date: 2026-02-15
type: implementation
status: resolved
session_id: -
services: [opencode, subprocess]
branch: -
tickets: [MNT-18]
tags: [streaming, subprocess, live-output]
related: []
---

# Subagent output streaming

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-10-fix-project-creation-timeouts]]. See wiki/archive/ for the
> original.

## TL;DR

Subagent (subprocess) output is now printed to the console near-realtime instead of being captured silently until completion. Streaming happens line-by-line inside `run_command` in `demetra/services/subprocess.py`, with a `live_stream` helper in `demetra/services/utils.py`; a `disable_stdio` flag turns streaming off for silent calls.

---

## Overview

The acceptance criteria: while a subagent runs, the operator sees near-realtime process output rather than a silent wait followed by a dump. This landed as part of the workflow modularization work (PR #9, MNT-37) but is tracked here as its own capability.

## Step 1 — Stream child process output line-by-line

**File:** `demetra/services/subprocess.py` — `run_command`

The child process `stdout` / `stderr` is read line-by-line and forwarded to the console as it is produced, rather than buffered until the process exits.

```python
# inside run_command, while reading child output:
for line in iter(child.stdout.readline, ""):
    live_stream(line, ...)   # print to console / session log
```

## Step 2 — Add `live_stream` helper and `disable_stdio` opt-out

**File:** `demetra/services/utils.py` — `live_stream`

- `live_stream` centralizes how a streamed line is emitted (console output, and later the session log).
- `run_command` accepts a `disable_stdio` flag so silent calls (e.g. cleanup, background helpers) suppress live output while still capturing the full output for return.

## Step 3 — Apply streaming to subagent runs

Workflow steps that invoke a subagent pass output through the streaming path, so plan / build / review agent runs stream live while still returning the captured `stdout`/`stderr` tuple for further processing.

## Test Results

Subprocess behavior is covered by the integration/unit tests added in the same modularization effort (MNT-21/MNT-37) around subprocess running and output capture.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-18
