---
title: Linear link artifact
generated: {by: demetra, at: '2026-06-22T00:00:00Z'}
description: Records MNT-114 adding a `linear_link` field to `sessions` via migration, populated on first task save, returned by the API and rendered as a 'View Linear Issue' link in the React artifacts block; archived with content merged into the research-plan artifact page.
type: implementation
status: deprecated
session_id: '-'
services: [database, api, react]
branch: '-'
tickets: [MNT-114, MNT-108]
tags: [linear-link, artifact, react, artifacts, pr-link, build-plan]
related: [2026-06-09-build-artifacts.md, 2026-09-14-research-plan-artifact.md]
---

# Linear link artifact

> **Archived on 2026-11-15.** Useful info merged into
> [2026-09-14-research-plan-artifact](/pages/2026-09-14-research-plan-artifact.md). See wiki/archive/ for the original.

## TL;DR

Session artifacts now include a "View Linear Issue" link. A `linear_link` field was added to `sessions` (migration), set on first save when the Linear task is retrieved, returned by the API, and rendered in the React artifacts section.

---

## Overview

Artifact block showed PR link and build plan (MNT-108) but not the originating Linear ticket. This adds the ticket link.

## Changes

- **Persist** (`sessions` model + migration): `linear_link` field, populated on first save once Linear task is retrieved.
- **API** (`api`): session response includes `linear_link`.
- **Frontend** (`react`): artifacts section renders "View Linear Issue" link.

## Test Results

Tests cover field population on first save, API payload, and rendered link.

---

## Source — [2026-06-09-build-artifacts](/archive/2026-06-09-build-artifacts.md)

Persisted `pr_link` + `build_plan` as session artifacts rendered in React top block. Originally decided in [2026-06-09-build-artifacts](/archive/2026-06-09-build-artifacts.md) on 2026-06-09.

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [2026-06-09-build-artifacts](/archive/2026-06-09-build-artifacts.md), [2026-09-14-research-plan-artifact](/pages/2026-09-14-research-plan-artifact.md)
- External: [MNT-114 — Linear link artifact (Linear)](https://linear.app/mnt/issue/MNT-114)
