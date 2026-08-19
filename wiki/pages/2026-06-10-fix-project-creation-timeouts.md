---
title: Fix Project creation timeouts
date: 2026-06-10
type: implementation
status: resolved
session_id: "-"
services: [subprocess, opencode, settings]
branch: "-"
tickets: [MNT-97, MNT-18]
tags: [timeout, subprocess, project-creation, bug, shell-tool, streaming, live-output]
related: [2026-02-15-subagent-output-streaming.md]
---

# Fix Project creation timeouts

## TL;DR

Project creation was timing out because `run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to OpenCode agent/subprocess calls too, killing long operations like clone and build. The fix removed the explicit short timeout from the OpenCode callers in `demetra/services/opencode.py`, renamed the setting `SHELL_TIMEOUT_MS` to `SUBPROCESS_TIMEOUT` (seconds) in `demetra/settings.py`, and made `run_command`'s default timeout the `SUBPROCESS_TIMEOUT`. Project-creation error handling in `demetra/services/project.py` was also tightened.

This page merges MNT-112 (`2026-06-09-increase-shell-tool-timeout-120s.md`), which first introduced the configurable timeout protection; MNT-97 reworked that same setting. Both modify the same `run_command` timeout in `demetra/services/subprocess.py` — there is no separate agent-tool-layer timeout.

---

## Overview

Root cause: a single short timeout was applied indiscriminately to every subprocess, including long-lived OpenCode agent runs. The fix separates the default subprocess timeout from any short-lived shell timeout.

- `run_command` applied the 120s `SHELL_TIMEOUT_MS` to OpenCode calls, killing clone/build
- Explicit short timeout removed from OpenCode callers
- Setting renamed `SHELL_TIMEOUT_MS` -> `SUBPROCESS_TIMEOUT` (seconds, default 1800)
- `run_command` default timeout now the `SUBPROCESS_TIMEOUT`
- Project-creation error handling tightened

## Step 1 — Configurable timeout protection (MNT-112)

**File:** `demetra/services/subprocess.py`

Long-running commands inside the agent tool layer were being killed at a hard 120s safety limit. MNT-112 added timeout protection to the subprocess runner: commands that exceed the configured timeout are terminated and the call returns a timeout status instead of a truncated/hung result. The timeout defaulted to 2 minutes and was overridable via environment so deployments running heavier builds could raise it without a code change. Tests covered the termination path and the timeout-status return value.

## Step 2 — Root cause (MNT-97)

`run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to all subprocesses. Long project-creation operations — `git clone`, dependency build — exceeded it and were killed.

## Step 3 — OpenCode callers

**File:** `demetra/services/opencode.py`

Removed the explicit short timeout from the OpenCode agent/subprocess callers so they inherit the longer default.

## Step 4 — Setting rename

**File:** `demetra/settings.py`

Renamed `SHELL_TIMEOUT_MS` to `SUBPROCESS_TIMEOUT`, now expressed in seconds, and made it the default timeout used by `run_command`. The current default is 1800s.

## Step 5 — Error handling

Tightened project-creation error handling in `demetra/services/project.py` so provisioning failures surface cleanly instead of as generic timeouts.

## Test Results

Tests cover the termination path and the timeout-status return value (MNT-112) plus the OpenCode-caller timeout removal.

---

## Source — [[2026-02-15-subagent-output-streaming]]

Originally added in [[2026-02-15-subagent-output-streaming]] on 2026-02-15 (MNT-18):
`run_command` in `demetra/services/subprocess.py` streams child `stdout`/`stderr`
**line-by-line** to the console near-realtime instead of buffering until exit, via a
`live_stream` helper in `demetra/services/utils.py`. A `disable_stdio` flag turns live
output off for silent calls (cleanup, background helpers) while still returning the full
captured `stdout`/`stderr` tuple. All plan/build/review agent runs stream through this
path.

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-97, MNT-112
