---
title: Linear link artifact
date: 2026-06-22
type: implementation
status: resolved
session_id: "-"
services: [database, api, react]
branch: "-"
tickets: [MNT-114, MNT-108]
tags: [linear-link, artifact, react, artifacts, pr-link, build-plan]
related: [2026-06-09-build-artifacts.md, 2026-09-14-research-plan-artifact.md]
---

# Linear link artifact

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

## Source — [[2026-06-09-build-artifacts]]

Persisted `pr_link` + `build_plan` as session artifacts rendered in React top block. Originally decided in [[2026-06-09-build-artifacts]] on 2026-06-09.

## Follow-ups

None.

## References

- Related: [[2026-09-14-research-plan-artifact]]
- External: [MNT-114 — Linear link artifact (Linear)](https://linear.app/mnt/issue/MNT-114)
