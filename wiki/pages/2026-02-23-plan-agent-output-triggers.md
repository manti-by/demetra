---
title: Plan agent output triggers
date: 2026-02-23
type: implementation
status: resolved
session_id: -
services: [main, workflows, linear]
branch: -
tickets: [MNT-30]
tags: [plan, triggers, auto-mode, questions]
related: [2026-07-16-fix-empty-build-plan-loop]
---

# Plan agent output triggers

## TL;DR

After the empty-state check, the workflow inspects the extracted plan to decide what happens next: `PLAN_IS_READY_STRING` triggers an automatic build with no user input; `PLAN_HAS_QUESTIONS` extracts the questions, posts them to Linear, and moves the ticket to an awaiting-input state. A `--auto` flag runs this headless. When questions are present, the build plan is not posted to Linear. See also [[2026-07-16-fix-empty-build-plan-loop]].

---

## Overview

MNT-30 turns the plan agent's output markers into workflow triggers, so the loop can advance automatically (or park waiting for input) without an operator watching.

## Step 1 — Trigger automatic build on ready plan

When the extracted plan contains `PLAN_IS_READY_STRING`, the workflow proceeds straight into the build step without prompting the user.

## Step 2 — Handle plans that have questions

When `PLAN_HAS_QUESTIONS` is present:

- extract the questions from the plan output
- post them as a Linear comment on the ticket
- move the ticket to an awaiting-input state
- do **not** post the build plan to Linear (only the questions)

## Step 3 — Add the `--auto` flag

**File:** `main.py`

`--auto` runs the loop headless: in auto mode questions are posted to Linear and the workflow exits (with cleanup); without it, the loop waits for user input.

## Test Results

Tests were added covering the ready-plan and questions triggers, including the awaiting-input transition and the no-plan-post-when-questions rule.

---

## Follow-ups

None.

## References

- Related: [[2026-07-16-fix-empty-build-plan-loop]]
- External: https://linear.app/mnt/issue/MNT-30
