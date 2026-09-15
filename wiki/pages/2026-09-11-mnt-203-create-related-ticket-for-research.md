---
title: 'MNT-203: Create related ticket for research'
date: '2026-09-11'
type: implementation
status: resolved
session_id: ses_f6ef2a998ffefbAQfDD0V9gPcN
services: [.coderabbit, .gitattributes, .gitignore, AGENTS, Makefile, README, bootstrap,
  api, listener, react, rq-dashboard, watcher, worker, library, queries, linear/__init__,
  linear/mutations, linear/tasks, persistence/database, runtime/project, vcs/github,
  settings, tools, workflows, a3b4c5d6e7f8_add_sessions_research_report_column, pyproject,
  App, SessionArtifacts.test, SessionList.test, index, conftest, test_database, test_docstring_tools,
  test_github, test_linear, test_project, test_wiki_tools, test_workflows, uv, INDEX,
  QUESTIONS, 2026-06-25-update-project-version, 2026-08-07-mnt-147-wiki-processes-pr70-review,
  2026-08-19-build-agent-stale-session-deleted-worktree, 2026-08-21-mnt-176-bump-version-error,
  2026-08-28-awaiting-input-workflow-continues-to-review, 2026-08-31-mnt-192-env-edit-button,
  2026-09-08-docstring-mcp-search, 2026-09-10-mnt-200-update-research-loop, 2026-09-11-mnt-203-create-related-ticket-for-research]
branch: mnt-203-create-related-ticket-for-research
tickets: [MNT-203]
tags: [wiki, feature]
related: [2026-09-01-mnt-177-research-loop]
---
# MNT-203: Create related ticket for research

## TL;DR

The session implemented a feature to create a related Linear ticket for research results instead of adding them as comments to the original ticket. The new ticket is created in the same project, priority, and state, with the required labels. All tests have passed, and a wiki page has been added to document the change.

---

## Overview

The implementation involved updating the `LinearTask` model, extending `LinearConfig`, and creating a new `create_research_ticket` helper function. Key files changed include `demetra/library/models.py`, `demetra/services/linear/mutations.py`, and `demetra/workflows/research.py`. A wiki page was also created to document the change, including the steps taken and the results of the tests.

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
- `demetra/library/exceptions.py` (4/0)
- `demetra/library/models.py` (1/2)
- `demetra/library/tables.py` (0/1)
- `demetra/library/types.py` (2/0)
- `demetra/queries/get_issue_by_title.gql` (9/0)
- `demetra/services/linear/__init__.py` (2/0)
- `demetra/services/linear/mutations.py` (118/1)
- `demetra/services/linear/tasks.py` (2/0)
- `demetra/services/persistence/database.py` (1/32)
- `demetra/services/runtime/project.py` (5/18)
- `demetra/services/vcs/github.py` (0/4)
- `demetra/settings.py` (2/42)
- `demetra/tools/docstrings.py` (0/363)
- `demetra/tools/registry.py` (4/11)
- `demetra/tools/search.py` (0/19)
- `demetra/tools/wiki.py` (50/10)
- `demetra/workflows/research.py` (133/30)
- `migrations/versions/a3b4c5d6e7f8_add_sessions_research_report_column.py` (0/32)
- `pyproject.toml` (0/1)
- `react/src/App.css` (0/9)
- `react/src/components/SessionArtifacts.test.tsx` (0/1)
- `react/src/components/SessionList.test.tsx` (0/5)
- `react/src/index.css` (0/4)
- `react/src/services/api.ts` (0/1)
- `tests/conftest.py` (5/2)
- `tests/test_database.py` (0/48)
- `tests/test_docstring_tools.py` (0/110)
- `tests/test_github.py` (0/4)
- `tests/test_linear.py` (294/1)
- `tests/test_project.py` (4/24)
- `tests/test_wiki_tools.py` (2/3)
- `tests/test_workflows.py` (173/57)
- `uv.lock` (1/27)
- `wiki/INDEX.md` (6/9)
- `wiki/QUESTIONS.md` (0/8)
- `wiki/pages/2026-06-25-update-project-version.md` (2/11)
- `wiki/pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md` (1/1)
- `wiki/pages/2026-08-19-build-agent-stale-session-deleted-worktree.md` (0/2)
- `wiki/pages/2026-08-21-mnt-176-bump-version-error.md` (2/9)
- `wiki/pages/2026-08-28-awaiting-input-workflow-continues-to-review.md` (0/2)
- `wiki/pages/2026-08-31-mnt-192-env-edit-button.md` (1/1)
- `wiki/pages/2026-09-08-docstring-mcp-search.md` (0/120)
- `wiki/pages/2026-09-10-mnt-200-update-research-loop.md` (0/112)
- `wiki/pages/2026-09-11-mnt-203-create-related-ticket-for-research.md` (192/0)

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

 demetra/library/exceptions.py                      |   4 +

 demetra/library/models.py                          |   3 +-

 demetra/library/tables.py                          |   1 -

 demetra/library/types.py                           |   2 +

 demetra/queries/get_issue_by_title.gql             |   9 +

 demetra/services/linear/__init__.py                |   2 +

 demetra/services/linear/mutations.py               | 119 ++++++-

 demetra/services/linear/tasks.py                   |   2 +

 demetra/services/persistence/database.py           |  33 +-

 demetra/services/runtime/project.py                |  23 +-

 demetra/services/vcs/github.py                     |   4 -

 demetra/settings.py                                |  44 +--

 demetra/tools/docstrings.py                        | 363 ---------------------

 demetra/tools/registry.py                          |  15 +-

 demetra/tools/search.py                            |  19 --

 demetra/tools/wiki.py                              |  60 +++-

 demetra/workflows/research.py                      | 163 +++++++--

 ...c5d6e7f8_add_sessions_research_report_column.py |  32 --

 pyproject.toml                                     |   1 -

 react/src/App.css                                  |   9 -

 react/src/components/SessionArtifacts.test.tsx     |   1 -

 react/src/components/SessionList.test.tsx          |   5 -

 react/src/index.css                                |   4 -

 react/src/services/api.ts                          |   1 -

 tests/conftest.py                                  |   7 +-

 tests/test_database.py                             |  48 ---

 tests/test_docstring_tools.py                      | 110 -------

 tests/test_github.py                               |   4 -

 tests/test_linear.py                               | 295 ++++++++++++++++-

 tests/test_project.py                              |  28 +-

 tests/test_wiki_tools.py                           |   5 +-

 tests/test_workflows.py                            | 230 +++++++++----

 uv.lock                                            |  28 +-

 wiki/INDEX.md                                      |  15 +-

 wiki/QUESTIONS.md                                  |   8 -

 wiki/pages/2026-06-25-update-project-version.md    |  13 +-

 ...026-08-07-mnt-147-wiki-processes-pr70-review.md |   2 +-

 ...9-build-agent-stale-session-deleted-worktree.md |   2 -

 .../pages/2026-08-21-mnt-176-bump-version-error.md |  11 +-

 ...-awaiting-input-workflow-continues-to-review.md |   2 -

 wiki/pages/2026-08-31-mnt-192-env-edit-button.md   |   2 +-

 wiki/pages/2026-09-08-docstring-mcp-search.md      | 120 -------

 .../2026-09-10-mnt-200-update-research-loop.md     | 112 -------

 ...1-mnt-203-create-related-ticket-for-research.md | 192 +++++++++++

 57 files changed, 1180 insertions(+), 1157 deletions(-)
```

## Build plan

## Implementation Plan
### Overview

The implementation plan involves creating a related Linear ticket for research results instead of adding them as comments to the original ticket. The new ticket will be in the same Linear project, have the same priority, be in the `PRD` state, and include the `Feature` label along with any `Backend` or `Frontend` labels from the source ticket.

### Key Steps

1. **Add `linear_project_id` to `LinearTask` model**: Extend the `LinearTask` model with an optional `linear_project_id` field to store the Linear project ID.
2. **Populate `linear_project_id`**: Update `get_todo_issues` and `get_linear_task_by_id` to populate the `linear_project_id` field.
3. **Extend `LinearConfig`**: Add `backend_label_id` and `frontend_label_id` fields to `LinearConfig` to stor…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f6ef2a998ffefbAQfDD0V9gPcN`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-203/create-related-ticket-for-research
