---
title: Refactor workflow into modular steps
date: 2026-02-23
type: implementation
status: resolved
session_id: -
services: [main, workflows]
branch: -
tickets: [MNT-37]
tags: [refactor, modules, workflow]
related: []
---

# Refactor workflow into modular steps

## TL;DR

The monolithic workflow in `main.py` was refactored into readable, modular steps under `demetra/workflows/*.py`: a worktree creation helper, an integrated plan agent, an automated linter/test runner, and finalize actions (commit & push, PR creation, centralized cleanup). Error handling is consolidated and finalization is unified across every workflow path. This is the basis of the current `demetra/workflows/` layout.

---

## Overview

MNT-37 is the structural refactor that turns the single-file supervisor into the modular step layout still in use today, without changing workflow behavior.

## Step 1 — Worktree creation helper

A dedicated module wraps git worktree creation, encapsulating the `git worktree add` mechanics behind a single helper.

## Step 2 — Integrated plan agent

The plan step becomes a self-contained module that runs the plan agent, extracts the plan (MNT-20), and applies the output triggers (MNT-30).

## Step 3 — Automated linter / test runner

The lint + test feedback loop from MNT-21 lives in its own module, returning failures into the build loop.

## Step 4 — Finalize actions

Finalization is centralized and unified across all workflow paths:

- commit & push
- PR creation (MNT-31)
- centralized cleanup (MNT-19)

## Step 5 — Consolidated error handling

Error handling is unified so every path through the workflow terminates through the same finalize/cleanup machinery instead of bespoke per-branch handling.

## Test Results

The refactor is covered by the integration + unit test suites built up in MNT-21 (linting, testing, workflow, subprocess behavior); all pass after the modularization.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-37
