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
related: []
---

# Update project version

## TL;DR

Added automatic version bumping in `pyproject.toml` on every feature/bugfix workflow. New features and bugs trigger a minor bump; tickets carrying the `EPIC` label trigger a major bump. The bump is integrated into the workflow with automatic rollback on workflow failure. Tests added.

---

## Overview

The project version previously only changed on manual intervention. The workflow now bumps it deterministically based on the ticket type.

## Step 1 — Version bump service

Added a service that bumps the project version in `pyproject.toml`:

- minor bump for every new feature or bug,
- major bump when the ticket carries the `EPIC` label.

## Step 2 — Integrate into the workflow

**File:** `workflows`

The bump runs as part of the workflow. If the workflow fails, the version change is automatically rolled back so a failed run does not leave a version bump behind.

## Step 3 — Epic releases

Epic releases trigger the major increment path, keeping the versioning in step with ticket scope.

## Test Results

Tests cover the bump logic (minor vs major) and the rollback on workflow failure.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-116 — Update project version (Linear)](https://linear.app/mnt/issue/MNT-116)
