---
title: Process manager
date: 2026-03-02
type: implementation
status: resolved
session_id: -
services: [watcher, main]
branch: -
tickets: [MNT-40]
tags: [daemon, systemd, polling, parallelism]
related: []
---

# Process manager

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-08-10-docker-compose-deploy]]. See wiki/archive/ for the
> original.

## TL;DR

A system daemon (`watcher.py`) polls the Linear TODO column every 5 minutes and spawns a workflow subprocess per new task, up to `num_cpu - 1` in parallel. A `status` column (pending/processed/failed) was added to the `sessions` table, and a systemd service config was added under `configs/`. Tasks are marked processed only after a successful workflow; failed subprocesses are not retried — the ticket is moved back to TODO.

---

## Overview

MNT-40 turns Demetra from a one-shot CLI into a supervised daemon that picks up new work automatically and runs tickets in parallel.

## Step 1 — Add `watcher.py` poll loop

**File:** `watcher.py` (project root)

An infinite loop polls every 5 minutes:

```python
while True:
    issues = get_todo_issues(...)   # project list from the Linear query
    for issue in issues:
        spawn_workflow(issue)       # one subprocess per task
    time.sleep(5 * 60)
```

`get_todo_issues()` is unchanged — it iterates over the project list from the Linear query.

## Step 2 — Parallel workflow spawn

A separate workflow subprocess is spawned per new task, capped at `num_cpu - 1` concurrent runs. Async where possible inside the poll loop.

## Step 3 — Add `status` column to `sessions`

**File:** database migration

`status` tracks each session as `pending` / `processed` / `failed`.

- a task is marked `processed` only after a successful workflow
- a failed subprocess is not retried — the ticket is moved back to TODO for the next poll

## Step 4 — systemd service config

**File:** `configs/`

A systemd unit runs `watcher.py` as a service so the daemon survives reboots and restarts.

## Test Results

Tests cover the poll loop, parallel spawning bounds, and status transitions (pending → processed/failed).

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-40
