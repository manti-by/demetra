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

Sessions with plan-agent questions no longer flip to `Failed` — they now enter an `Awaiting Input` state (stored as `step="awaiting_input"`). Workflows can record custom failure states, and cleanup/history preserve awaiting-input status instead of overwriting it.

---

## Overview

When the plan agent posted clarifying questions and moved the Linear ticket to `Awaiting Input`, the session was marked `Failed` — conflating "waiting on user" with "broken".

## Changes

- **Session state**: added `Awaiting Input` distinct from `Failed` (`step="awaiting_input"` in `StepType`, see [[2026-08-05-pr-creation-failure-handler]]).
- **Set after questions** (`workflows`): after posting questions to Linear and moving the ticket, session is set to `Awaiting Input`.
- **Custom failure states + cleanup**: workflows record custom states; tasks in `Awaiting Input` keep it through cleanup/history updates.

## Test Results

Tests cover new state, transition after posting questions, and preservation through cleanup/history.

---

## Source — [[2026-02-23-plan-agent-output-triggers]]

MNT-30 (2026-02-23): plan output markers drive workflow — `PLAN_IS_READY_STRING` auto-builds with no input; `PLAN_HAS_QUESTIONS` extracts questions, posts as Linear comment, moves ticket to awaiting-input without posting the build plan. `--auto` runs headless; interactive loop waits for input. MNT-140 made awaiting-input a first-class `Session` state.

## Follow-ups

None.

## References

- Related: none
- External: [MNT-140 — Awaiting Input status for session (Linear)](https://linear.app/mnt/issue/MNT-140)
