---
title: Build artifacts
date: 2026-06-09
type: implementation
status: resolved
session_id: "-"
services: [database, api, react]
branch: "-"
tickets: [MNT-108]
tags: [artifacts, pr-link, build-plan, react]
related: []
---

# Build artifacts

## TL;DR

Session artifacts — the PR link and the build plan — are now persisted and shown in the React app. Added `pr_link` to the `session` model with an Alembic migration; the field is populated when a PR is successfully created via `gh`. The API returns `pr_link` and `build_plan`, the frontend stores both and renders an artifact block at the top of the session log. Tests on both FE and BE.

---

## Overview

Previously the PR link and build plan were not surfaced to the user in the session view. This change persists them and adds a dedicated artifacts block in the UI.

## Step 1 — Persist the PR link

**File:** `session` model + Alembic migration

Added a `pr_link` field to the `session` model. When a PR is successfully created via `gh`, the workflow writes the PR URL into `pr_link`.

## Step 2 — Return artifacts from the API

**File:** `api`

The session API now returns both `pr_link` and `build_plan` so the frontend has everything it needs to render the artifact block.

## Step 3 — Show artifacts in the React app

**File:** `react`

The frontend stores `pr_link` and `build_plan` in the browser and renders a block at the top of the session log:

- the PR link opens in a new window,
- the build plan opens a modal showing the plan text.

## Test Results

Tests on both frontend (artifact block rendering, modal open) and backend (API payload includes `pr_link` and `build_plan`, field set on PR creation).

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-108 — Build artifacts (Linear)](https://linear.app/mnt/issue/MNT-108)
