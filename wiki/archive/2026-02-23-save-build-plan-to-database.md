---
title: Save build plan to a database
date: 2026-02-23
type: implementation
status: resolved
session_id: -
services: [database, sessions, workflows]
branch: -
tickets: [MNT-39]
tags: [database, build-plan, persistence]
related: []
---

# Save build plan to a database

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-07-16-fix-empty-build-plan-loop]]. See wiki/archive/ for the
> original.

## TL;DR

The build plan is persisted to the database, and the plan step is skipped on the next run if a plan already exists. The `sessions` table gained `build_plan` (text) and `posted_to_linear` (bool) columns; `upsert_pending_session` persists the plan; the setup step checks for an existing plan and skips planning; `posted_to_linear` prevents double-posting to Linear. Tests included.

---

## Overview

MNT-39 makes the plan durable across runs: once planned, a ticket does not get re-planned, and the plan is not re-posted to Linear.

## Step 1 — Extend the `sessions` table

**File:** database migration

- `build_plan` (text) — the persisted plan body
- `posted_to_linear` (bool) — whether the plan was already posted to the Linear ticket (MNT-29)

## Step 2 — Persist the plan on session upsert

**File:** `upsert_pending_session`

When a plan is produced, it is stored on the pending session row along with the `posted_to_linear` flag state.

## Step 3 — Skip planning when a plan exists

The setup step checks for an existing plan for the ticket; if one exists, the plan step is skipped and the stored plan is reused for the build.

## Step 4 — Prevent double-posting

`posted_to_linear` gates the MNT-29 post so the plan is only posted once across runs.

## Test Results

Tests cover session upsert persistence of the plan, the skip-planning-on-existing-plan behavior, and the double-post guard.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-39
