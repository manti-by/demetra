---
title: Add multiagent code review
date: 2026-02-23
type: implementation
status: resolved
session_id: -
services: [workflows, review]
branch: -
tickets: [MNT-35]
tags: [review, multiagent, cursor, coderabbit]
related: []
---

# Add multiagent code review

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-05-25-async-review]]. See wiki/archive/ for the
> original.

## TL;DR

Code changes are now reviewed by three agents — opencode, cursor, and coderabbit — whose output is consolidated into one set of comments. The consolidated comments go back to the build agent; if there are none, the workflow proceeds to lint. Build and review steps were moved into separate files, and agent role config was added to control tool permissions.

---

## Overview

MNT-35 replaces a single-reviewer model with a multiagent review pass: three independent review agents look at the diff, and their findings are merged before deciding the next step.

## Step 1 — Split build and review into separate modules

**File:** `demetra/` (workflow steps)

The build and review steps moved out of `main.py` into their own files, so each stage is a self-contained unit (a precursor to the full `demetra/workflows/` layout in MNT-37).

## Step 2 — Run three review agents

The review step runs three agents against the changes:

- **opencode** — in-repo coding agent
- **cursor** — Cursor review
- **coderabbit** — CodeRabbit AI review (see `.coderabbit.yaml` from MNT-21)

## Step 3 — Consolidate results

All three agents' comments are consolidated into a single set. The workflow then either:

- sends the consolidated comments back to the build agent for another iteration, or
- proceeds to lint if there are no comments

## Step 4 — Agent role config

Role-based config controls tool permissions for the plan / build / review roles, so each agent only gets the tools its role needs.

## Test Results

Verified through workflow runs exercising both branches (comments → back to build; no comments → proceed to lint).

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-35
