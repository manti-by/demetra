---
title: 'MNT-200: Update research loop'
generated: {by: demetra, at: '2026-09-10T00:00:00Z'}
description: MNT-200 added a sessions.research_report column (migration a3b4c5d6e7f8) and a navy-blue researched step badge to replace post-research awaiting_input; later notes show its researched-as-terminal claim was superseded by MNT-203 and MNT-232, though researched remains a valid StepType that is now written again.
type: implementation
status: stable
session_id: ses_f7309e1b6ffes6G5sccIOnOCdh
services: [workflows, persistence, library, api, react, wiki]
branch: mnt-200-update-research-loop
tickets: [MNT-200]
tags: [research, research-loop, persistence, sessions]
related: [2026-09-01-mnt-177-research-loop.md, 2026-11-12-ch-11-failed-status-for-awaiting-input-tickets.md, 2026-10-12-session-state-flow-feedback-loops.md, 2026-09-11-mnt-203-create-related-ticket-for-research.md, 2026-09-14-research-plan-artifact.md, 2026-10-05-mnt-232-update-research-flow.md]
---

# MNT-200: Update research loop

## TL;DR

Research loop now persists the extracted report to new `sessions.research_report` column and uses a new `researched` StepType (navy-blue badge). Added migration, StepType/Session updates, and React/CSS changes. Tests green.

---

## Overview

Adds `research_report` persistence and `researched` step to replace post-research `awaiting_input`. Key files: `demetra/library/tables.py`, `demetra/library/models.py`, `demetra/services/persistence/database.py`, `react/src/App.css`/`index.css`, `migrations/versions/a3b4c5d6e7f8_add_sessions_research_report_column.py`.

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

> **Consistency fix (2026-09-18, Consistency Agent):** Supersedes 2026-09-15 note. Verified against HEAD (`demetra/library/tables.py:35`, migration `a3b4c5d6e7f8`): only `research_report` exists; `research_plan`/`8023ece…` from [2026-09-14-research-plan-artifact](/pages/2026-09-14-research-plan-artifact.md) is not in HEAD. Earlier "both coexist" claim was based on that branch, not current HEAD.

> **Consistency note (2026-10-06, Consistency Agent):** the "rename post-research step
> to `researched`" claim above is superseded by
> [2026-09-11-mnt-203-create-related-ticket-for-research](/pages/2026-09-11-mnt-203-create-related-ticket-for-research.md) (`14d0d02`): the
> current flow ends with `step="awaiting_input"`
> (`demetra/workflows/research.py:199`), not `step="researched"`. `researched`
> remains a valid `StepType` (`demetra/library/models.py:27`) with badge CSS, but
> nothing writes it.
>
> **Consistency note (2026-10-08, Consistency Agent):** the 2026-10-06 note
> above is itself superseded by [2026-10-05-mnt-232-update-research-flow](/pages/2026-10-05-mnt-232-update-research-flow.md)
> (PR #135, merged): `step="researched"` now has a writer
> (`demetra/workflows/research.py:230`, after the Linear move to In Review
> succeeds). Terminal state is In Review / `researched`, not `awaiting_input`.

## References

- Related: [2026-09-01-mnt-177-research-loop](/pages/2026-09-01-mnt-177-research-loop.md), [2026-11-12-ch-11-failed-status-for-awaiting-input-tickets](/pages/2026-11-12-ch-11-failed-status-for-awaiting-input-tickets.md), [2026-10-12-session-state-flow-feedback-loops](/pages/2026-10-12-session-state-flow-feedback-loops.md), [2026-09-11-mnt-203-create-related-ticket-for-research](/pages/2026-09-11-mnt-203-create-related-ticket-for-research.md), [2026-10-05-mnt-232-update-research-flow](/pages/2026-10-05-mnt-232-update-research-flow.md)
- External: https://linear.app/mnt/issue/MNT-200/update-research-loop
