---
title: Awaiting Input status for session
date: 2026-07-21
type: implementation
status: resolved
session_id: -
services: [sessions, workflows, linear]
branch: -
tickets: [MNT-140]
tags: [awaiting-input, session-status, linear]
related: []
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

## Follow-ups

None.

## References

- Related: none
- External: [MNT-140 — Awaiting Input status for session (Linear)](https://linear.app/mnt/issue/MNT-140)
