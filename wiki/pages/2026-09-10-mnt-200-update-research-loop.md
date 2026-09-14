---
title: 'MNT-200: Update research loop'
date: '2026-09-10'
type: implementation
status: resolved
session_id: ses_f7309e1b6ffes6G5sccIOnOCdh
services: [workflows, persistence, library, api, react, wiki]
branch: mnt-200-update-research-loop
tickets: [MNT-200]
tags: [research, research-loop, persistence, sessions]
related: [2026-09-01-mnt-177-research-loop.md, 2026-07-21-awaiting-input-status-for-session.md, 2026-07-16-fix-step-status-review-findings.md]
---
# MNT-200: Update research loop

## TL;DR

The research loop has been updated to save research results to a new session database field and introduce a new 'researched' step. The changes include updates to workflow Python files, a new migration, and a wiki page. The outcome is a more streamlined research process with improved tracking and visualization. All tests have passed, verifying the changes.

---

## Overview

The implementation involved adding a new 'research_report' column to the sessions table, updating the StepType and Session models, and introducing a new 'researched' step with a navy-blue label. Key changes were made to files such as 'demetra/library/tables.py', 'demetra/services/persistence/database.py', and 'react/src/App.css', with new tests added to 'tests/test_workflows.py' to ensure the changes work as expected.

## Changed files

- `.opencode/package-lock.json` (8/8)
- `demetra/library/models.py` (2/0)
- `demetra/library/tables.py` (1/0)
- `demetra/services/persistence/database.py` (32/1)
- `demetra/workflows/research.py` (8/5)
- `migrations/versions/a3b4c5d6e7f8_add_sessions_research_report_column.py` (32/0)
- `pyproject.toml` (1/1)
- `react/src/App.css` (9/0)
- `react/src/components/SessionArtifacts.test.tsx` (1/0)
- `react/src/components/SessionList.test.tsx` (5/0)
- `react/src/index.css` (4/0)
- `react/src/services/api.ts` (1/0)
- `tests/test_database.py` (48/0)
- `tests/test_workflows.py` (53/4)
- `uv.lock` (2/2)
- `wiki/INDEX.md` (3/1)
- `wiki/pages/2026-09-10-mnt-200-update-research-loop.md` (145/0)

## Stat

```text
.opencode/package-lock.json                        |  16 +--

 demetra/library/models.py                          |   2 +

 demetra/library/tables.py                          |   1 +

 demetra/services/persistence/database.py           |  33 ++++-

 demetra/workflows/research.py                      |  13 +-

 ...c5d6e7f8_add_sessions_research_report_column.py |  32 +++++

 pyproject.toml                                     |   2 +-

 react/src/App.css                                  |   9 ++

 react/src/components/SessionArtifacts.test.tsx     |   1 +

 react/src/components/SessionList.test.tsx          |   5 +

 react/src/index.css                                |   4 +

 react/src/services/api.ts                          |   1 +

 tests/test_database.py                             |  48 +++++++

 tests/test_workflows.py                            |  57 +++++++-

 uv.lock                                            |   4 +-

 wiki/INDEX.md                                      |   4 +-

 .../2026-09-10-mnt-200-update-research-loop.md     | 145 +++++++++++++++++++++

 17 files changed, 355 insertions(+), 22 deletions(-)
```

## Build plan

## Implementation Plan
### Approach
The approach involves persisting the extracted research report to a new `sessions.research_report` column, replacing the post-research step name `awaiting_input` with a new `researched` StepType, and adding a navy-blue CSS color for the new step badge in the React sidebar.

### Steps
1. **Add `research_report` column to `sessions` table**: Update `demetra/library/tables.py` to add a new column `research_report` with `Text()` type and `nullable=True`.
2. **Create migration for `research_report` column**: Create a new Alembic migration in `migrations/versions/` to add the `research_report` column to `sessions`.
3. **Update `StepType` and `Session` models**: Update `demetra/library/models.py` to add `"researched"` to the `StepType` Literal and add `research…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f7309e1b6ffes6G5sccIOnOCdh`

---

## Follow-ups

- None

> **Consistency fix (2026-09-11, Consistency Agent):** `services` frontmatter was a file-list dump (`package-lock`, `INDEX`, etc.); corrected to `[workflows, persistence, library, api, react, wiki]`. `tags` refined to `[research, research-loop, persistence, sessions]`. Added missing body links to mirror `related` frontmatter.

## References

- Related: [[2026-09-01-mnt-177-research-loop]], [[2026-07-21-awaiting-input-status-for-session]], [[2026-07-16-fix-step-status-review-findings]]
- External: https://linear.app/mnt/issue/MNT-200/update-research-loop
