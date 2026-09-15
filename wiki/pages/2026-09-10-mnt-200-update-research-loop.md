---
title: 'MNT-200: Update research loop'
date: '2026-09-10'
type: implementation
status: resolved
session_id: ses_f7309e1b6ffes6G5sccIOnOCdh
services:
- workflows
- persistence
- library
- api
- react
- wiki
branch: mnt-200-update-research-loop
tickets:
- MNT-200
tags:
- research
- research-loop
- persistence
- sessions
related:
- 2026-09-01-mnt-177-research-loop.md
- 2026-07-21-awaiting-input-status-for-session.md
- 2026-07-16-fix-step-status-review-findings.md
- 2026-09-11-mnt-203-create-related-ticket-for-research.md
- 2026-09-14-research-plan-artifact.md
---
# MNT-200: Update research loop

## TL;DR

Research loop now persists the extracted report to new `sessions.research_report` column and uses a new `researched` StepType (navy-blue badge). Added migration, StepType/Session updates, and React/CSS changes. Tests green.

---

## Overview

Adds `research_report` persistence and `researched` step to replace post-research `awaiting_input`. Key files: `demetra/library/tables.py`, `demetra/library/models.py`, `demetra/services/persistence/database.py`, `react/src/App.css`/`index.css`, `migrations/versions/a3b4c5d6e7f8_add_sessions_research_report_column.py`.

## Changed files

- `.opencode/package-lock.json`, `pyproject.toml`, `uv.lock`, `wiki/INDEX.md`
- `demetra/library/models.py` (2/0) — `StepType += "researched"`, `Session.research_report`
- `demetra/library/tables.py` (1/0) — `research_report Text() nullable`
- `demetra/services/persistence/database.py` (32/1), `demetra/workflows/research.py` (8/5)
- `migrations/versions/a3b4c5d6e7f8_add_sessions_research_report_column.py` (32/0)
- `react/src/App.css` (9/0), `react/src/index.css` (4/0), `react/src/services/api.ts` (1/0)
- `react/src/components/SessionArtifacts.test.tsx`, `SessionList.test.tsx`, `tests/test_database.py` (48/0), `tests/test_workflows.py` (53/4)
- 17 files, 355 insertions(+), 22 deletions(-)

## Build plan

Persist extracted report to `sessions.research_report`, rename post-research step to `researched`, add navy-blue badge.

1. Add `research_report Text() nullable` to `sessions` in `demetra/library/tables.py`.
2. Migration in `migrations/versions/`.
3. Update `StepType` + `Session` in `demetra/library/models.py`.
4. Update persistence + workflow + React badge/CSS + API.

## Test Results

- Session `resolved`, OpenCode `ses_f7309e1b6ffes6G5sccIOnOCdh`

> **Consistency fix (2026-09-11):** `services` frontmatter corrected from file-list dump to `[workflows, persistence, library, api, react, wiki]`; tags refined; body links added.

---

## Follow-ups

- None

> **Consistency note (2026-09-15, Consistency Agent):** `research_report` (`a3b4c5…`) persists here; [[2026-09-14-research-plan-artifact]] (this branch `mnt-204-research-result-modal`) adds parallel `research_plan` (`8023ece…`) column — both exist in `demetra/library/tables.py:27,36` on this branch, not a rename/revert. Earlier "reverted scaffolding" claim in [[2026-09-11-mnt-203-create-related-ticket-for-research]] refers to that branch's diff, not current HEAD where both columns coexist.

## References

- Related: [[2026-09-01-mnt-177-research-loop]], [[2026-07-21-awaiting-input-status-for-session]], [[2026-07-16-fix-step-status-review-findings]]
- External: https://linear.app/mnt/issue/MNT-200/update-research-loop
