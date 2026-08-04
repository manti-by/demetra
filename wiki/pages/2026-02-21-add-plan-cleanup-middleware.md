---
title: Add plan cleanup middleware
date: 2026-02-21
type: implementation
status: resolved
session_id: -
services: [opencode, workflows]
branch: -
tickets: [MNT-20]
tags: [plan, extraction, build-plan]
related: [2026-07-16-fix-empty-build-plan-loop]
---

# Add plan cleanup middleware

## TL;DR

A clean build plan is now extracted from the plan agent's raw output before anything downstream uses it. `extract_plan()` in `demetra/services/opencode.py` looks for the plan markers and trims the text; it is called from `main.py` before the build step so the cleaned plan feeds user-facing messages, Linear posts, and the build prompt. Empty plans halt further processing — see [[2026-07-16-fix-empty-build-plan-loop]].

---

## Overview

The plan agent produces a verbose transcript; downstream consumers need only the plan portion. MNT-20 adds a middleware step that extracts and normalizes the plan between the plan agent and the build step.

## Step 1 — Implement `extract_plan`

**File:** `demetra/services/opencode.py`

```python
def extract_plan(output: str, ...) -> str | None:
    # search for PLAN_HEADER_STRING / PLAN_IS_READY_STRING / PLAN_HAS_QUESTIONS
    # trim surrounding text and return the clean plan body
```

`PLAN_IS_READY_STRING` marks a finalized plan; `PLAN_HAS_QUESTIONS` marks a plan that needs answers (used by MNT-30's triggers). The extracted text excludes agent chatter around the plan markers.

## Step 2 — Call extraction in `main.py` before the build step

The cleaned plan is used consistently everywhere it matters:

- user-facing console messages
- the plan posted to Linear
- the build prompt sent to the build agent

## Step 3 — Empty-plan guard

If `extract_plan` returns nothing (no ready marker found), further processing halts instead of feeding an empty plan into the build step.

## Test Results

Tests in `tests/test_opencode.py` cover stored-plan reuse and empty-plan detection (empty plans are recognized and halt processing).

---

## Follow-ups

None.

## References

- Related: [[2026-07-16-fix-empty-build-plan-loop]]
- External: https://linear.app/mnt/issue/MNT-20
