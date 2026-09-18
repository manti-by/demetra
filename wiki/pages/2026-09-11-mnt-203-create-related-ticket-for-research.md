---
title: 'MNT-203: Create related ticket for research'
date: 2026-09-11
type: implementation
status: resolved
session_id: ses_f6ef2a998ffefbAQfDD0V9gPcN
services:
- api
- react
- library
- settings
- tools
- workflows
branch: mnt-203-create-related-ticket-for-research
tickets:
- MNT-203
tags:
- wiki
- feature
related:
- 2026-09-01-mnt-177-research-loop
- 2026-09-10-mnt-200-update-research-loop.md
- 2026-09-14-research-plan-artifact.md
---
# MNT-203: Create related ticket for research

## TL;DR

Research workflow now creates a related Linear ticket instead of posting a comment on the source ticket. New ticket inherits project, priority, and state (`PRD`), with `Feature` plus source `Backend`/`Frontend` labels. Added `linear_project_id` to `LinearTask`, `backend/frontend_label_id` to `LinearConfig`, and `create_research_ticket` helper.

---

## Overview

Updates `demetra/library/models.py` (`LinearTask.linear_project_id`), `demetra/library/types.py` (`LinearConfig.backend/frontend_label_id`), `demetra/services/linear/mutations.py` (`create_research_ticket` 118/1), `demetra/services/linear/tasks.py`, `demetra/workflows/research.py` (133/30), `demetra/queries/get_issue_by_title.gql`, plus infra/config cleanup (`.coderabbit.yaml`, bootstrap, services). Reverted prior `research_report` scaffolding and docstring/search tooling in this diff.

## Build plan

Create related ticket in same project/priority/state, with `Feature` label plus `Backend`/`Frontend` from source.

1. Add `linear_project_id` to `LinearTask`.
2. Populate it in `get_todo_issues` / `get_linear_task_by_id`.
3. Extend `LinearConfig` with `backend_label_id` / `frontend_label_id`.
4. Implement `create_research_ticket` and wire into `research.py`.

## Changed files

57 files, 1180 insertions(+), 1157 deletions(-) — key: `demetra/services/linear/mutations.py` (119+), `demetra/workflows/research.py` (163+), `tests/test_linear.py` (294+), `tests/test_workflows.py` (173+); many reverted files from MNT-200/docstring branches.

## Test Results

- Session `resolved`, OpenCode `ses_f6ef2a998ffefbAQfDD0V9gPcN`

---

## Follow-ups

- None

> **Consistency fix (2026-09-18, Consistency Agent):** Supersedes 2026-09-15 note. HEAD retains `research_report` (`a3b4c5…`, `tables.py:35`); "reverted scaffolding" was branch-local (MNT-203 diff vs MNT-200). `research_plan`/`8023ece…` from [[2026-09-14-research-plan-artifact]] is not in HEAD — see that page's 2026-09-18 fix.

## References

- Related: [[2026-09-01-mnt-177-research-loop]], [[2026-09-10-mnt-200-update-research-loop]]
- External: https://linear.app/mnt/issue/MNT-203/create-related-ticket-for-research