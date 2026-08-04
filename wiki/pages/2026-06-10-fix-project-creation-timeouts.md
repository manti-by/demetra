---
title: Fix Project creation timeouts
date: 2026-06-10
type: implementation
status: resolved
session_id: -
services: [subprocess, opencode, settings]
branch: -
tickets: [MNT-97]
tags: [timeout, subprocess, project-creation, bug]
related: []
---

# Fix Project creation timeouts

## TL;DR

Project creation was timing out because `run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to OpenCode agent/subprocess calls too, killing long operations like clone and build. The fix removed the explicit short timeout from the OpenCode callers in `demetra/services/opencode.py`, renamed the setting `SHELL_TIMEOUT_MS` to `SUBPROCESS_TIMEOUT` (seconds) in `demetra/settings.py`, and made `run_command`'s default timeout the `SUBPROCESS_TIMEOUT`. Project-creation error handling in `demetra/services/project.py` was also tightened.

---

## Overview

Root cause: a single short timeout was applied indiscriminately to every subprocess, including long-lived OpenCode agent runs. The fix separates the default subprocess timeout from any short-lived shell timeout.

- `run_command` applied the 120s `SHELL_TIMEOUT_MS` to OpenCode calls, killing clone/build
- Explicit short timeout removed from OpenCode callers
- Setting renamed `SHELL_TIMEOUT_MS` -> `SUBPROCESS_TIMEOUT` (seconds)
- `run_command` default timeout now the `SUBPROCESS_TIMEOUT`
- Project-creation error handling tightened

## Step 1 — Root cause

`run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to all subprocesses. Long project-creation operations — `git clone`, dependency build — exceeded it and were killed.

## Step 2 — OpenCode callers

**File:** `demetra/services/opencode.py`

Removed the explicit short timeout from the OpenCode agent/subprocess callers so they inherit the longer default.

## Step 3 — Setting rename

**File:** `demetra/settings.py`

Renamed `SHELL_TIMEOUT_MS` to `SUBPROCESS_TIMEOUT`, now expressed in seconds, and made it the default timeout used by `run_command`.

## Step 4 — Error handling

Tightened project-creation error handling in `demetra/services/project.py` so provisioning failures surface cleanly instead of as generic timeouts.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-97
