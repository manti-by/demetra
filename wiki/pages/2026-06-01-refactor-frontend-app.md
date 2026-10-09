---
title: Refactor frontend app
date: 2026-06-01
type: implementation
status: resolved
session_id: '-'
services: [react]
branch: '-'
tickets: [MNT-77]
tags: [react, refactor, rename]
related: [2026-07-22-react-frontend-template-warp.md]
---

# Refactor frontend app

> **Consolidated 2026-09-02.** Still live in `wiki/pages/` — this is the session
> record, not an archived page. Its reusable content was merged into
> [[2026-07-22-react-frontend-template-warp]], the page to read for the current state of that subsystem.
> The `wiki/archive/` copy this banner used to point at was removed in
> `70144cb` (2026-09-18), so there is no separate original.

## TL;DR

Refactored and renamed the `hera` frontend app to `react`, normalizing the directory after `hera` had existed as an early scaffold. The rename touched the frontend directory, the Makefile, and docs. The same PR also enhanced GitHub auth validation (preventing unauthorized access attempts), removed legacy FastAPI docs, and bumped the version to 1.10.0.

---

## Overview

Cleanup ticket: the frontend had grown under a temporary `hera` name; this normalizes it to `react/` and tightens a couple of loose ends along the way.

- Frontend directory moved/renamed from `hera` to `react`
- Makefile + docs updated for the new name
- GitHub auth validation enhanced to prevent unauthorized access attempts
- Legacy FastAPI docs removed
- Version bumped to 1.10.0

## Step 1 — Rename `hera` to `react`

Moved and renamed the frontend directory from `hera` to `react`, normalizing the early scaffold to the canonical name.

## Step 2 — Makefile and docs

Updated the Makefile targets and documentation to reference the renamed frontend directory.

## Step 3 — Auth validation and cleanup

In the same PR:

- GitHub auth validation enhanced to reject unauthorized access attempts
- Legacy FastAPI docs removed
- Version bumped to 1.10.0

---

## Follow-ups

- None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-22-react-frontend-template-warp]]
- External: https://linear.app/mnt/issue/MNT-77
