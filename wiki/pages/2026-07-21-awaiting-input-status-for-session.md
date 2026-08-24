---
title: Awaiting Input status for session
date: 2026-07-21
type: implementation
status: resolved
session_id: "-"
services: [sessions, workflows, linear, main]
branch: "-"
tickets: [MNT-140, MNT-30]
tags: [awaiting-input, session-status, linear, plan, triggers, auto-mode, questions]
related: [2026-02-23-plan-agent-output-triggers.md, 2026-08-05-pr-creation-failure-handler.md]
---

# Awaiting Input status for session

## TL;DR

Sessions no longer flip to `Failed` when the plan agent has questions and moves the Linear ticket to `Awaiting Input`. A `Session` can now be in an `Awaiting Input` state, set right after questions are posted to Linear; workflows can record custom failure states, and tickets in Awaiting Input keep that status during cleanup and history updates. Tests added.

---

## Overview

Before this change, when the plan agent posted clarifying questions to Linear and moved the ticket to `Awaiting Input`, the session itself was marked `Failed`. That conflated "waiting on the user" with "broken", skewing history and cleanup.

## Step 1 — Add the Awaiting Input session state

**File:** `Session` model

Added an `Awaiting Input` state to `Session`, distinct from `Failed`.

## Step 2 — Set the state after posting questions

**File:** `workflows`

When the plan agent has questions, the workflow posts them to Linear (moving the ticket to `Awaiting Input`) and now also sets the session to the `Awaiting Input` state.

## Step 3 — Custom failure states + cleanup

Workflows can now record custom failure states instead of a single generic `Failed`. Tasks moved to `Awaiting Input` keep that status during cleanup and history updates, so they are not re-marked failed.

## Test Results

Tests cover the new session state, the transition after posting questions, and that Awaiting Input survives cleanup/history updates.

---

## Source — [[2026-02-23-plan-agent-output-triggers]]

Originally added in [[2026-02-23-plan-agent-output-triggers]] on 2026-02-23 (MNT-30):
the plan agent's output markers drive the workflow. `PLAN_IS_READY_STRING` triggers an
automatic build with no user input; when `PLAN_HAS_QUESTIONS` is present the workflow
extracts the questions, posts them as a Linear comment, and moves the ticket to an
awaiting-input state — and does **not** post the build plan (only the questions).
`--auto` runs this headless; interactively the loop waits for user input. This page
(MNT-140) later made that awaiting-input state a first-class `Session` state instead of
a generic `Failed`.

## Follow-ups

None.

> **Consistency note (2026-08-24, Consistency Agent):** "Awaiting Input" is stored as the `sessions.step` enum value `"awaiting_input"` (`StepType` in `demetra/library/models.py`), not a separate status column — see [[2026-08-05-pr-creation-failure-handler]].

## References

- Related: none
- External: [MNT-140 — Awaiting Input status for session (Linear)](https://linear.app/mnt/issue/MNT-140)
