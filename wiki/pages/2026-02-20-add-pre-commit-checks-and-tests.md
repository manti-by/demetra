---
title: Add pre-commit checks and tests
date: 2026-02-20
type: implementation
status: resolved
session_id: -
services: [workflows, lint]
branch: -
tickets: [MNT-21]
tags: [pre-commit, pytest, lint, ruff]
related: []
---

# Add pre-commit checks and tests

## TL;DR

After the build agent finishes, the workflow now runs `make check` (`ty` + pre-commit) and `make test` (pytest) via subprocess runners; on failure the output is fed back to the build agent for another iteration. Added `.coderabbit.yaml`, pytest auto-detection, and extensive integration + unit tests. Version bumped to 1.3.1.

---

## Overview

MNT-21 closes the loop between building and verifying: linting and tests run automatically after each build, and their failures become input for the next build iteration.

## Step 1 — Add subprocess runners for check and test

**File:** `demetra/workflows/` lint runner

- `make check` — runs `ty` type checking plus the pre-commit suite (Ruff lint + import management).
- `make test` — runs the pytest suite.
- pytest is auto-detected so the runner can fall back gracefully when the suite is absent.

## Step 2 — Feed failures back into the build loop

When check or test fails, the captured output is returned to the build agent as feedback, triggering another build→check iteration until the code passes.

## Step 3 — Add `.coderabbit.yaml`

Added the CodeRabbit review config so the AI review agent is configured project-wide.

## Test Results

Extensive integration + unit tests were added covering:

- linting (check) behavior
- test (pytest) running behavior
- workflow orchestration of the build→check loop
- subprocess runner behavior

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-21
