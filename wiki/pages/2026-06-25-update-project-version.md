---
title: Update project version
date: 2026-06-25
type: implementation
status: resolved
session_id: "-"
services: [workflows, settings]
branch: "-"
tickets: [MNT-116]
tags: [version, bump, pyproject]
related: [2026-08-21-mnt-176-bump-version-error.md]
---

# Update project version

## TL;DR

Added automatic version bumping in `pyproject.toml` on every feature/bugfix workflow. Every feature or bug triggers a minor bump; the major version is bumped manually only. The bump is integrated into the workflow with automatic rollback on workflow failure. Tests added.

---

## Overview

The project version previously only changed on manual intervention. The workflow now bumps the minor version deterministically on every feature/bugfix run.

## Step 1 — Version bump service

Added a service that bumps the project version in `pyproject.toml`:

- minor bump for every new feature or bug,
- the major version is preserved and bumped manually only.

## Step 2 — Integrate into the workflow

**File:** `workflows`

The bump runs as part of the workflow. If the workflow fails, the version change is automatically rolled back so a failed run does not leave a version bump behind.

## Step 3 — Major releases

Major version bumps are done manually only and are out of scope for the automatic workflow bump; the auto-bump always increments the minor version.

## Test Results

Tests cover the bump logic (minor bump, major preservation) and the rollback on workflow failure.

---

## Follow-ups

None.

## References

- Related: [[2026-08-21-mnt-176-bump-version-error]]
- External: [MNT-116 — Update project version (Linear)](https://linear.app/mnt/issue/MNT-116)
