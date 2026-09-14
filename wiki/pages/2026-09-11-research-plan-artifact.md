---
title: 'MNT-204: Research result modal'
date: '2026-09-14'
type: implementation
status: resolved
session_id: ses_f6ebf2b52ffeSrLs1KXvA5gPQI
services: [.coderabbit, .gitattributes, .gitignore, AGENTS, Makefile, README, bootstrap,
  api, listener, react, rq-dashboard, watcher, worker, library, persistence/database,
  runtime/project, vcs/github, settings, tools, workflows, 8023ece006bc_add_sessions_research_plan_column,
  pyproject, App, SessionArtifacts.test, SessionArtifacts, SessionList.test, index,
  test_database, test_docstring_tools, test_github, test_project, test_session_logging,
  test_wiki_tools, test_workflows, uv, INDEX, QUESTIONS, 2026-06-09-build-artifacts,
  2026-06-22-linear-link-artifact, 2026-06-25-update-project-version, 2026-08-07-mnt-147-wiki-processes-pr70-review,
  2026-08-19-build-agent-stale-session-deleted-worktree, 2026-08-21-mnt-176-bump-version-error,
  2026-08-28-awaiting-input-workflow-continues-to-review, 2026-08-31-mnt-192-env-edit-button,
  2026-09-08-docstring-mcp-search, 2026-09-10-mnt-200-update-research-loop, 2026-09-11-research-plan-artifact]
branch: mnt-204-research-result-modal
tickets: [MNT-204]
tags: [wiki, feature, frontend]
related: [2026-06-22-linear-link-artifact.md, 2026-06-09-build-artifacts.md, 2026-09-01-mnt-177-research-loop.md]
---
# MNT-204: Research result modal

## TL;DR

The research result modal feature has been implemented, allowing users to view research plans alongside build plans. The implementation includes updates to the database schema, dataclass, and persistence layer, as well as additions to the React UI and tests. The feature is now available in the React app, and all tests have passed.

---

## Overview

The implementation involved adding a research_plan column to the sessions table, updating the Session dataclass, and creating a new Alembic migration. The persistence layer was updated to include the research_plan column, and the research workflow was modified to persist the research report. The React UI now includes a View Research Plan link and modal, and tests were added to verify the feature's functionality.

## Changed files

- `.coderabbit.yaml` (0/2)
- `.gitattributes` (0/1)
- `.gitignore` (0/1)
- `AGENTS.md` (3/3)
- `Makefile` (24/12)
- `README.md` (0/1)
- `configs/bootstrap.sh` (16/0)
- `configs/services/api.service` (20/0)
- `configs/services/listener.service` (20/0)
- `configs/services/react.service` (21/0)
- `configs/services/rq-dashboard.service` (20/0)
- `configs/services/watcher.service` (20/0)
- `configs/services/worker.service` (20/0)
- `demetra/library/models.py` (1/2)
- `demetra/library/tables.py` (1/1)
- `demetra/services/persistence/database.py` (20/15)
- `demetra/services/runtime/project.py` (5/18)
- `demetra/services/vcs/github.py` (0/4)
- `demetra/settings.py` (0/42)
- `demetra/tools/docstrings.py` (0/363)
- `demetra/tools/registry.py` (4/11)
- `demetra/tools/search.py` (0/19)
- `demetra/tools/wiki.py` (50/10)
- `demetra/workflows/research.py` (6/7)
- `migrations/versions/{a3b4c5d6e7f8_add_sessions_research_report_column.py => 8023ece006bc_add_sessions_research_plan_column.py}` (6/6)
- `pyproject.toml` (0/1)
- `react/src/App.css` (4/9)
- `react/src/components/SessionArtifacts.test.tsx` (77/1)
- `react/src/components/SessionArtifacts.tsx` (43/1)
- `react/src/components/SessionList.test.tsx` (5/5)
- `react/src/index.css` (0/4)
- `react/src/services/api.ts` (1/1)
- `tests/test_database.py` (16/13)
- `tests/test_docstring_tools.py` (0/110)
- `tests/test_github.py` (0/4)
- `tests/test_project.py` (4/24)
- `tests/test_session_logging.py` (16/0)
- `tests/test_wiki_tools.py` (2/3)
- `tests/test_workflows.py` (16/26)
- `uv.lock` (1/27)
- `wiki/INDEX.md` (6/9)
- `wiki/QUESTIONS.md` (0/8)
- `wiki/pages/2026-06-09-build-artifacts.md` (2/2)
- `wiki/pages/2026-06-22-linear-link-artifact.md` (2/2)
- `wiki/pages/2026-06-25-update-project-version.md` (2/11)
- `wiki/pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md` (1/1)
- `wiki/pages/2026-08-19-build-agent-stale-session-deleted-worktree.md` (0/2)
- `wiki/pages/2026-08-21-mnt-176-bump-version-error.md` (2/9)
- `wiki/pages/2026-08-28-awaiting-input-workflow-continues-to-review.md` (0/2)
- `wiki/pages/2026-08-31-mnt-192-env-edit-button.md` (1/1)
- `wiki/pages/2026-09-08-docstring-mcp-search.md` (0/120)
- `wiki/pages/2026-09-10-mnt-200-update-research-loop.md` (0/112)
- `wiki/pages/2026-09-11-research-plan-artifact.md` (74/0)

## Stat

```text
.coderabbit.yaml                                   |   2 -

 .gitattributes                                     |   1 -

 .gitignore                                         |   1 -

 AGENTS.md                                          |   6 +-

 Makefile                                           |  36 +-

 README.md                                          |   1 -

 configs/bootstrap.sh                               |  16 +

 configs/services/api.service                       |  20 ++

 configs/services/listener.service                  |  20 ++

 configs/services/react.service                     |  21 ++

 configs/services/rq-dashboard.service              |  20 ++

 configs/services/watcher.service                   |  20 ++

 configs/services/worker.service                    |  20 ++

 demetra/library/models.py                          |   3 +-

 demetra/library/tables.py                          |   2 +-

 demetra/services/persistence/database.py           |  35 +-

 demetra/services/runtime/project.py                |  23 +-

 demetra/services/vcs/github.py                     |   4 -

 demetra/settings.py                                |  42 ---

 demetra/tools/docstrings.py                        | 363 ---------------------

 demetra/tools/registry.py                          |  15 +-

 demetra/tools/search.py                            |  19 --

 demetra/tools/wiki.py                              |  60 +++-

 demetra/workflows/research.py                      |  13 +-

 ...3ece006bc_add_sessions_research_plan_column.py} |  12 +-

 pyproject.toml                                     |   1 -

 react/src/App.css                                  |  13 +-

 react/src/components/SessionArtifacts.test.tsx     |  78 ++++-

 react/src/components/SessionArtifacts.tsx          |  44 ++-

 react/src/components/SessionList.test.tsx          |  10 +-

 react/src/index.css                                |   4 -

 react/src/services/api.ts                          |   2 +-

 tests/test_database.py                             |  29 +-

 tests/test_docstring_tools.py                      | 110 -------

 tests/test_github.py                               |   4 -

 tests/test_project.py                              |  28 +-

 tests/test_session_logging.py                      |  16 +

 tests/test_wiki_tools.py                           |   5 +-

 tests/test_workflows.py                            |  42 +--

 uv.lock                                            |  28 +-

 wiki/INDEX.md                                      |  15 +-

 wiki/QUESTIONS.md                                  |   8 -

 wiki/pages/2026-06-09-build-artifacts.md           |   4 +-

 wiki/pages/2026-06-22-linear-link-artifact.md      |   4 +-

 wiki/pages/2026-06-25-update-project-version.md    |  13 +-

 ...026-08-07-mnt-147-wiki-processes-pr70-review.md |   2 +-

 ...9-build-agent-stale-session-deleted-worktree.md |   2 -

 .../pages/2026-08-21-mnt-176-bump-version-error.md |  11 +-

 ...-awaiting-input-workflow-continues-to-review.md |   2 -

 wiki/pages/2026-08-31-mnt-192-env-edit-button.md   |   2 +-

 wiki/pages/2026-09-08-docstring-mcp-search.md      | 120 -------

 .../2026-09-10-mnt-200-update-research-loop.md     | 112 -------

 wiki/pages/2026-09-11-research-plan-artifact.md    |  74 +++++

 53 files changed, 532 insertions(+), 1026 deletions(-)
```

## Build plan

## Implementation Plan
### Approach
The approach is to mirror the existing `build_plan` artifact end-to-end for the research output. This involves persisting the extracted research report in a new `research_plan` column on `sessions`, surfacing it through the existing session API, and adding a "View Research Plan" link + modal in `SessionArtifacts` that reuses the same render/markdown toggle already used for the build plan.

### Key Technical Decisions
* The new artifact will be named `research_plan` to follow the same naming convention as `build_plan`.
* The modal title and link text will both read "Research Plan" to match the task description.

### Implementation Steps
1. **Schema**: Add a `research_plan` column to the `sessions` Table definition in `demetra/library/tables.py`.
2. **Data…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f6ebf2b52ffeSrLs1KXvA5gPQI`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-204/research-result-modal
