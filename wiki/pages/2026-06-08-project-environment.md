---
title: Project environment
date: 2026-06-08
type: implementation
status: resolved
session_id: -
services: [database, subprocess, workflows]
branch: -
tickets: [MNT-110]
tags: [environment, subprocess, per-project]
related: []
---

# Project environment

## TL;DR

Added per-project environment variables that are applied to every subprocess the supervisor spawns. A new `Environment` model (`project_id` FK, `key`, `value`) holds one-to-many records per project; the `Project` dataclass in `Context` builds a cached `environment` dict from them and it is passed wherever a subprocess runs. Migration + tests. MNT-109 was the earlier partial attempt (PR #49, closed).

---

## Overview

Different projects need different environment variables (tokens, paths, flags). Previously every subprocess inherited only the supervisor process environment. This change makes project settings reach git, workflow steps, and agent commands.

## Step 1 — Persist environment records

**File:** `Environment` model

New model with `project_id` FK, `key`, and `value` — one project maps to many environment records. Alembic migration included.

## Step 2 — Expose a cached environment dict

**File:** `Project` dataclass in `Context`

`Project` gains a cached `environment` dict built from the linked `Environment` records. The records are fetched right after `Project` on session setup, so they are available before the workflow starts.

## Step 3 — Pass environment to every subprocess

**File:** `subprocess` runner / workflow steps

The environment is passed everywhere a subprocess is spawned:

- git,
- CI / workflow steps,
- code-analysis, lint, and test,
- agent commands.

Review/build/resolve workflows and agent executions honor the overrides.

## Test Results

Tests cover the `Environment` model, the cached dict construction, and that subprocess calls receive the merged per-project environment.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-110 — Project environment (Linear)](https://linear.app/mnt/issue/MNT-110)
