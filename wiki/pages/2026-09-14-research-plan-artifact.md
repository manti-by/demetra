---
title: 'MNT-204: Research result modal'
generated: {by: demetra, at: '2026-09-14T00:00:00Z'}
description: MNT-204 added a View Research Plan modal in SessionArtifacts and a sessions.research_plan column with migration 8023ece006bc, mirroring build_plan end-to-end across schema, workflow, API and UI; the work was reverted the next day by af8970e, so HEAD keeps sessions.research_report (a3b4c5d6e7f8) and this page records a superseded artifact.
type: implementation
status: stable
session_id: ses_f6ebf2b52ffeSrLs1KXvA5gPQI
services: [api, library, persistence, workflows, react, settings]
branch: mnt-204-research-result-modal
tickets: [MNT-204, MNT-114, MNT-108]
tags: [wiki, feature, frontend, linear-link, artifacts, pr-link, react]
related: [2026-06-22-linear-link-artifact.md, 2026-06-09-build-artifacts.md, 2026-09-01-mnt-177-research-loop.md, 2026-09-10-mnt-200-update-research-loop.md]
---

# MNT-204: Research result modal

## TL;DR

Added "View Research Plan" link + modal mirroring the build-plan artifact — new `sessions.research_plan` column, Session persistence, API exposure, and `SessionArtifacts` UI with markdown toggle. Migration renamed to `8023ece006bc_add_sessions_research_plan_column`.

---

## Overview

Mirrors `build_plan` end-to-end for research output: schema → dataclass → persistence → workflow → React UI → tests.

## Build plan

1. Add `research_plan` column to `sessions` (`demetra/library/tables.py`).
2. Update `Session` dataclass + persistence + migration.
3. Persist report in `research.py` workflow.
4. Surface via API + `SessionArtifacts` "View Research Plan" modal reusing build-plan render/markdown toggle.

---

## Test Results

- Session `resolved`, OpenCode `ses_f6ebf2b52ffeSrLs1KXvA5gPQI`

## Source — [2026-06-22-linear-link-artifact](/archive/2026-06-22-linear-link-artifact.md)

Session artifacts are persisted as `sessions` columns rendered in the React top block: `pr_link` + `build_plan` ([2026-06-09-build-artifacts](/archive/2026-06-09-build-artifacts.md), MNT-108) and `linear_link` — the "View Linear Issue" link, populated on first save once the Linear task is retrieved (MNT-114, 2026-06-22). `research_plan` (this page, MNT-204) follows the same pattern. Originally decided in [2026-06-22-linear-link-artifact](/archive/2026-06-22-linear-link-artifact.md).

## Follow-ups

- None

> **Consistency fix (2026-09-18, Consistency Agent; refined 2026-09-28):** Codebase on HEAD uses `sessions.research_report` (`demetra/library/tables.py:35`, `models.py:134`, migration `a3b4c5d6e7f8`), not `research_plan`/`8023ece…` described above. [2026-09-10-mnt-200-update-research-loop](/pages/2026-09-10-mnt-200-update-research-loop.md) is the current persisted column; the `research_plan` rename was merged as `7a5ee99` but backed out the next day by `af8970e` ("MNT-204: Fix tests"), which deleted the `8023ece…` migration and restored `research_report` (see `demetra/services/persistence/database.py:596` `update_session_research_report`).

## References

- Related: [2026-06-22-linear-link-artifact](/archive/2026-06-22-linear-link-artifact.md), [2026-06-09-build-artifacts](/archive/2026-06-09-build-artifacts.md), [2026-09-01-mnt-177-research-loop](/pages/2026-09-01-mnt-177-research-loop.md)
- External: https://linear.app/mnt/issue/MNT-204/research-result-modal

> **Consistency note (2026-11-11, Consistency Agent):** The work described in this page was **reverted**: the `sessions.research_plan` column and its migration `8023ece006bc` no longer exist — HEAD keeps `sessions.research_report` (`demetra/library/tables.py:35`, migration `a3b4c5d6e7f8`), written by `update_session_research_report` (`demetra/services/persistence/database.py:596`). The `research_plan` rename landed as `7a5ee99` and was backed out the next day by `af8970e` (“MNT-204: Fix tests”). The page title (“Research result modal”) also does not match its TL;DR (“View Research Plan”).
