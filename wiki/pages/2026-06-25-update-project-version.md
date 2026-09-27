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
related:
- 2026-07-22-warp-theme-review-fixes-and-ops.md
- 2026-08-21-mnt-176-bump-version-error.md
- 2026-09-08-docstring-mcp-search.md
---

# Update project version

## TL;DR

Every feature/bugfix workflow now auto-bumps `pyproject.toml`; major bumps are manual. The bump is integrated into the workflow with rollback on failure. Tests added.

---

## Overview

Version previously changed only manually. Now the workflow bumps deterministically on every feature/bugfix run.

## Changes

- **Bump service**: increments version in `pyproject.toml` (minor per feature/bug; major manual only).
- **Workflow integration** (`workflows`): bump runs as part of workflow; rolled back on failure so failed runs leave no version change.
- **Major releases**: manual only, out of scope for auto-bump.

## Test Results

Tests cover bump logic (minor bump, major preservation) and rollback on failure.

## Consistency note (2026-08-23)

- Original MNT-116 (`ad2cf2a`) shipped a **major** bump for `EPIC`-labelled tickets (`is_epic_label` / `bump_project_version(..., is_epic=...)`) — the "major manual only" wording never fully matched code. [[2026-07-22-warp-theme-review-fixes-and-ops]] hardened `bump_project_version` to log+return `None` instead of raising.
- Epic branch removed 2026-08-21 in MNT-176 ([[2026-08-21-mnt-176-bump-version-error]], `fe33701`): always bumps minor now; `is_epic_label`/`EPIC_LABEL` removed.

## Consistency note (2026-09-11, Consistency Agent)

- Superseded by [[2026-09-08-docstring-mcp-search]] (`dd4f152`): reworked to explicit `is_major`/`is_minor`/`is_patch` flags (default `is_patch=True`). Default auto-bump now increments **patch** (`1.14.1 → 1.14.2`), not minor; minor-bump wording above is stale.

---

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-21-mnt-176-bump-version-error]], [[2026-09-08-docstring-mcp-search]]
- External: [MNT-116 — Update project version (Linear)](https://linear.app/mnt/issue/MNT-116)
