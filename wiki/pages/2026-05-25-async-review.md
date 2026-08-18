---
title: Async review
date: 2026-05-25
type: implementation
status: resolved
session_id: -
services: [workflows, review]
branch: -
tickets: [MNT-87, MNT-35]
tags: [review, async, parallelism, multiagent, cursor, coderabbit]
related: [2026-02-23-add-multiagent-code-review.md]
---

# Async review

## TL;DR

Made the code-review step parallel: `run_review_agents` now runs all review agents asynchronously and merges their responses. The same PR (with MNT-86) fixed `merge_review_results` to handle `None` stdout/stderr, fixed the test mocks, prevented empty commits by validating staged changes, and added the session delete button styling.

---

## Overview

Review agents previously ran sequentially, multiplying wall-clock time by the number of agents. Running them concurrently cuts review latency and merges the findings into one result.

- `run_review_agents` runs all agents in parallel
- `merge_review_results` handles `None` stdout/stderr
- Empty commits prevented by validating staged changes
- Test mocks fixed

## Step 1 — Parallel review agents

**File:** `demetra/workflows/review.py`

Updated `run_review_agents` to launch all review agents concurrently and collect their responses, then merge the findings into a single review result.

## Step 2 — Merge robustness

Fixed `merge_review_results` to handle `None` stdout/stderr from agents that produced no output, instead of assuming a string.

## Step 3 — No empty commits

Added staged-change validation so the workflow never creates a commit when there is nothing to commit.

## Step 4 — Test mocks and styling

Fixed the review test mocks to match the parallel execution, and added the session delete button styling shared with MNT-86.

## Test Results

Review tests were updated and pass with the parallel execution model.

---

## Source — [[2026-02-23-add-multiagent-code-review]]

Originally added in [[2026-02-23-add-multiagent-code-review]] on 2026-02-23 (MNT-35):
the review stage runs **three agents — opencode, cursor, and coderabbit** — and
consolidates their output into one set of comments. The consolidated comments go back
to the build agent for another iteration; if there are none, the workflow proceeds to
lint. Build and review steps were moved out of `main.py` into their own files here (a
precursor to the full `demetra/workflows/` layout of MNT-37), and role-based agent
config controls tool permissions per role (plan/build/review).

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-87
