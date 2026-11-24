---
title: Create GitHub PR
generated: {by: demetra, at: '2026-02-21T00:00:00Z'}
description: Records MNT-31 automating GitHub PR creation after `git push` via a `create_pull_request` service wrapping the `gh` CLI keyed off the branch name, with a configurable `GH_PATH` defaulting to `/usr/bin/gh`; the URL is printed and the run proceeds to In Review, with tests and later archival.
type: implementation
status: deprecated
session_id: '-'
services: [github, workflows]
branch: '-'
tickets: [MNT-31]
tags: [github, pr, gh]
related: []
---

# Create GitHub PR

> **Archived on 2026-08-18.** Useful info merged into
> [2026-08-05-pr-creation-failure-handler](/pages/2026-08-05-pr-creation-failure-handler.md). See wiki/archive/ for the
> original.

## TL;DR

After `git push`, the workflow now automatically creates a GitHub PR using the `gh` CLI, keyed off the branch name. The PR URL is printed and the run continues (including the ticket status update to `In Review`). A new `GH_PATH` setting (default `/usr/bin/gh`) configures the CLI path. Tests cover the service.

---

## Overview

MNT-31 closes the loop after the push: instead of leaving PR creation to the operator, the workflow opens the PR itself and reports the URL.

## Step 1 — Add the PR creation service

**File:** `demetra/services/github.py`

```python
def create_pull_request(branch_name: str, ...) -> tuple[int, str, str]:
    # gh pr create --head <branch_name> ...
    # returns (exit_code, stdout, stderr)
```

The service shells out to the `gh` CLI to create the PR from `branch_name`.

## Step 2 — Configure the `gh` path

**File:** `demetra/settings.py`

Added `GH_PATH` setting (default `/usr/bin/gh`) so the CLI location is configurable per environment.

## Step 3 — Wire into `main.py` after `git_push`

**File:** `main.py`

After the branch is pushed:

- the PR service creates the PR
- the workflow prints the PR URL
- the run proceeds, including the Linear status update to `In Review` (MNT-23)

## Test Results

Tests cover the GitHub PR service (branch-name input, `gh` invocation, exit-code/stdout/stderr contract).

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-31
