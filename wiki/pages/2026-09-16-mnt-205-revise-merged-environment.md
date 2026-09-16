---
title: 'MNT-205: Revise merged environment'
date: '2026-09-16'
type: implementation
status: resolved
session_id: ses_f55832b3effeWJy0LClcVV2V83
services: [.coderabbit, .gitattributes, .gitignore, build-agent, merge-agent, plan-agent,
  rebase-agent, research-agent, resolve-agent, review-agent, validate-agent, AGENTS,
  Makefile, README, bootstrap, api, listener, react, rq-dashboard, watcher, worker,
  library, queries, agents/opencode, daemons/watcher, linear/__init__, linear/config,
  linear/mutations, linear/tasks, llm/__init__, llm/config, llm/factory, llm/openrouter,
  persistence/database, runtime/project, runtime/utils, vcs/github, vcs/merge, vcs/rebase,
  wiki/render, settings, tools, workflows, docker-compose, main, a3b4c5d6e7f8_add_sessions_research_report_column,
  pyproject, App, LogConsole, SessionArtifacts.test, SessionArtifacts, SessionList.test,
  index, conftest, test_api_coverage, test_database, test_docstring_tools, test_github,
  test_linear, test_more_coverage, test_opencode, test_openrouter, test_project, test_rebase_service,
  test_session_environment, test_settings_layers, test_validate_workflow, test_wiki_tools,
  test_workflows, uv, app, appearance, core-plugins, graph, workspace, .sessions,
  INDEX, QUESTIONS, 2026-09-03-wiki-search-vs-bm25, 2026-06-02-delete-session-button,
  2026-06-02-plan-loop-resolve-questions, 2026-06-02-truncate-session-name, 2026-06-03-context-bloating,
  2026-06-03-fix-squash-migrations, 2026-06-04-review-summarization, 2026-06-08-max-run-attempts-for-a-ticket,
  2026-06-08-project-environment, 2026-06-08-session-step-attribute, 2026-06-09-build-artifacts,
  2026-06-09-check-linear-ticket-text, 2026-06-09-markdown-renderer, 2026-06-10-fix-project-creation-timeouts,
  2026-06-15-remove-patches-from-tests, 2026-06-22-github-pr-description, 2026-06-22-linear-link-artifact,
  2026-06-25-update-project-version, 2026-06-25-websocket-to-track-session-statuses,
  2026-07-07-add-context-compaction, 2026-07-07-project-deploy-script, 2026-07-15-duplicated-log-messages,
  2026-07-16-fix-empty-build-plan-loop, 2026-07-16-fix-notification-mark-read, 2026-07-16-fix-step-status-review-findings,
  2026-07-16-session-history-tokens-null, 2026-07-16-simplify-session-logging-setup,
  2026-07-20-resolve-ansi-color-escape-codes-in-logs, 2026-07-21-awaiting-input-status-for-session,
  2026-07-21-rich-markuperror-and-run-attempts, 2026-07-22-feature-flag-settings-and-tests,
  2026-07-22-react-frontend-template-warp, 2026-07-22-warp-theme-review-fixes-and-ops,
  2026-07-23-agents-md-revalidation-and-docs-removal, 2026-07-23-linear-ticket-email-password-auth,
  2026-07-23-session-history-modal, 2026-07-23-session-tokens-audit-revalidation,
  2026-07-24-plain-auth-review-followups, 2026-08-03-auth-hardening-and-deps-bump,
  2026-08-03-check-api-auth-and-credentials, 2026-08-03-favicon-set-and-react-html,
  2026-08-03-fix-mcp-server-2.0-api, 2026-08-03-wiki-mcp-tools, 2026-08-04-fix-resolve-agent-truncated-context,
  2026-08-05-post-build-validation, 2026-08-05-pr-creation-failure-handler, 2026-08-06-allowlist-review-fixes,
  2026-08-07-mnt-147-wiki-processes-pr70-review, 2026-08-07-split-wiki-service-into-subpackage,
  2026-08-09-apply-code-review-findings, 2026-08-09-apply-pr75-coderabbit-findings,
  2026-08-09-wiki-fixes-and-test-optimization, 2026-08-10-docker-compose-deploy, 2026-08-10-process-environment-3-layers-encryption-uv-venv,
  2026-08-17-docker-setup-review, 2026-08-18-categorize-settings-env-vars-by-layer,
  2026-08-18-compose-anchors-refactor, 2026-08-18-migrate-llm-groq-to-openrouter,
  2026-08-18-test-db-isolation-logging, 2026-08-19-build-agent-server-error-handler,
  2026-08-19-build-agent-stale-session-deleted-worktree, 2026-08-19-split-auth-linear-services-and-review-failure-handling,
  2026-08-19-wiki-should-use-llm-rename, 2026-08-19-worker-opencode-home-permissions,
  2026-08-20-fix-allowlist-tests, 2026-08-20-review-gh-auth-mount-changes, 2026-08-21-mnt-176-bump-version-error,
  2026-08-24-gh-config-dir-permission-entrypoint, 2026-08-24-guard-empty-plan-output,
  2026-08-25-loader-styleguide, 2026-08-25-mnt-181-total-tokens-counter, 2026-08-25-mnt-187-wiki-pages-not-generated,
  2026-08-28-awaiting-input-workflow-continues-to-review, 2026-08-28-fix-index-lock-concurrency,
  2026-08-28-mnt-177-workflow-blocked-openrouter-403, 2026-08-28-mnt-188-waitlist,
  2026-08-28-mnt-191-ticket-status-not-changed, 2026-08-31-mnt-192-env-edit-button,
  2026-09-01-mnt-177-research-loop, 2026-09-02-mobile-template-react-frontend, 2026-09-02-review-findings-cleanup,
  2026-09-08-docstring-mcp-search, 2026-09-08-opencode-reasoning-token-zero, 2026-09-10-mnt-200-update-research-loop,
  2026-09-11-mnt-203-create-related-ticket-for-research, 2026-09-14-listener-readline-limit-crash,
  2026-09-14-opencode-agent-prompts-hardening, 2026-09-14-research-plan-artifact,
  2026-09-16-mnt-205-context-environment]
branch: mnt-205-revise-merged-environment
tickets: [MNT-205]
tags: [wiki, backend, feature]
related: []
---
# MNT-205: Revise merged environment

## TL;DR

The implementation standardized methods for resolving agent models, Linear settings, and OpenRouter settings by introducing a single SessionEnvironment resolver. This resolver is exposed as the environment property on the Context object, allowing all workflow steps and helpers to read from the same place. The outcome is a more streamlined and efficient way of managing environment settings. All tests have passed, and the necessary wiki pages have been updated.

---

## Overview

The SessionEnvironment resolver was implemented in demetra/library/models.py, which looks up workflow environment keys through three layers: project environment, user-shared environment, and settings defaults. Key files and components updated include demetra/library/exceptions.py, demetra/services/agents/opencode.py, and demetra/services/linear/config.py. The changes aim to provide a unified way of accessing environment settings across the application.

## Changed files

- `.coderabbit.yaml` (0/2)
- `.gitattributes` (0/1)
- `.gitignore` (0/1)
- `.opencode/agents/build-agent.md` (1/14)
- `.opencode/agents/merge-agent.md` (3/18)
- `.opencode/agents/plan-agent.md` (6/20)
- `.opencode/agents/rebase-agent.md` (0/29)
- `.opencode/agents/research-agent.md` (2/8)
- `.opencode/agents/resolve-agent.md` (1/13)
- `.opencode/agents/review-agent.md` (3/15)
- `.opencode/agents/validate-agent.md` (2/14)
- `AGENTS.md` (16/18)
- `Makefile` (25/15)
- `README.md` (0/1)
- `configs/bootstrap.sh` (16/0)
- `configs/services/api.service` (20/0)
- `configs/services/listener.service` (20/0)
- `configs/services/react.service` (21/0)
- `configs/services/rq-dashboard.service` (20/0)
- `configs/services/watcher.service` (20/0)
- `configs/services/worker.service` (20/0)
- `demetra/library/exceptions.py` (3/3)
- `demetra/library/models.py` (189/4)
- `demetra/library/tables.py` (0/1)
- `demetra/library/types.py` (0/2)
- `demetra/queries/get_issue_by_title.gql` (0/9)
- `demetra/queries/update_issue.gql` (0/10)
- `demetra/services/agents/opencode.py` (31/93)
- `demetra/services/daemons/watcher.py` (24/9)
- `demetra/services/linear/__init__.py` (0/4)
- `demetra/services/linear/config.py` (0/36)
- `demetra/services/linear/mutations.py` (15/156)
- `demetra/services/linear/tasks.py` (4/4)
- `demetra/services/llm/__init__.py` (0/2)
- `demetra/services/llm/config.py` (0/30)
- `demetra/services/llm/factory.py` (7/6)
- `demetra/services/llm/openrouter.py` (25/24)
- `demetra/services/persistence/database.py` (1/36)
- `demetra/services/runtime/project.py` (5/18)
- `demetra/services/runtime/utils.py` (0/4)
- `demetra/services/vcs/github.py` (0/4)
- `demetra/services/vcs/merge.py` (3/2)
- `demetra/services/vcs/rebase.py` (7/6)
- `demetra/services/wiki/render.py` (1/1)
- `demetra/settings.py` (0/44)
- `demetra/tools/docstrings.py` (0/363)
- `demetra/tools/registry.py` (4/11)
- `demetra/tools/search.py` (0/19)
- `demetra/tools/wiki.py` (50/10)
- `demetra/workflows/build.py` (5/5)
- `demetra/workflows/cleanup.py` (3/4)
- `demetra/workflows/failure.py` (11/6)
- `demetra/workflows/merge.py` (4/2)
- `demetra/workflows/plan.py` (18/10)
- `demetra/workflows/rebase.py` (4/2)
- `demetra/workflows/research.py` (29/145)
- `demetra/workflows/resolve.py` (1/1)
- `demetra/workflows/review.py` (4/3)
- `demetra/workflows/review_fixes.py` (4/2)
- `demetra/workflows/validate.py` (4/3)
- `docker-compose.yaml` (0/2)
- `main.py` (6/6)
- `migrations/versions/a3b4c5d6e7f8_add_sessions_research_report_column.py` (0/32)
- `pyproject.toml` (1/2)
- `react/src/App.css` (1/14)
- `react/src/components/LogConsole.tsx` (1/1)
- `react/src/components/SessionArtifacts.test.tsx` (0/79)
- `react/src/components/SessionArtifacts.tsx` (1/43)
- `react/src/components/SessionList.test.tsx` (0/5)
- `react/src/index.css` (0/4)
- `react/src/services/api.ts` (0/1)
- `tests/conftest.py` (2/5)
- `tests/test_api_coverage.py` (12/12)
- `tests/test_database.py` (1/49)
- `tests/test_docstring_tools.py` (0/110)
- `tests/test_github.py` (0/4)
- `tests/test_linear.py` (10/316)
- `tests/test_more_coverage.py` (5/1)
- `tests/test_opencode.py` (35/34)
- `tests/test_openrouter.py` (10/10)
- `tests/test_project.py` (4/24)
- `tests/test_rebase_service.py` (3/3)
- `tests/test_session_environment.py` (223/0)
- `tests/test_settings_layers.py` (42/171)
- `tests/test_validate_workflow.py` (1/1)
- `tests/test_wiki_tools.py` (2/3)
- `tests/test_workflows.py` (35/242)
- `uv.lock` (2/28)
- `wiki/.obsidian/app.json` (0/3)
- `wiki/.obsidian/appearance.json` (0/1)
- `wiki/.obsidian/core-plugins.json` (0/33)
- `wiki/.obsidian/graph.json` (0/22)
- `wiki/.obsidian/workspace.json` (0/199)
- `wiki/.sessions.json` (1/3)
- `wiki/INDEX.md` (145/128)
- `wiki/QUESTIONS.md` (0/11)
- `wiki/audits/2026-09-03-wiki-search-vs-bm25.md` (0/176)
- `wiki/{archive => pages}/2026-06-02-delete-session-button.md` (0/0)
- `wiki/{archive => pages}/2026-06-02-plan-loop-resolve-questions.md` (0/2)
- `wiki/{archive => pages}/2026-06-02-truncate-session-name.md` (0/2)
- `wiki/{archive => pages}/2026-06-03-context-bloating.md` (0/2)
- `wiki/{archive => pages}/2026-06-03-fix-squash-migrations.md` (0/0)
- `wiki/{archive => pages}/2026-06-04-review-summarization.md` (0/2)
- `wiki/{archive => pages}/2026-06-08-max-run-attempts-for-a-ticket.md` (0/2)
- `wiki/{archive => pages}/2026-06-08-project-environment.md` (0/2)
- `wiki/{archive => pages}/2026-06-08-session-step-attribute.md` (0/2)
- `wiki/{archive => pages}/2026-06-09-build-artifacts.md` (2/4)
- `wiki/{archive => pages}/2026-06-09-check-linear-ticket-text.md` (0/0)
- `wiki/{archive => pages}/2026-06-09-markdown-renderer.md` (0/2)
- `wiki/{archive => pages}/2026-06-10-fix-project-creation-timeouts.md` (0/0)
- `wiki/pages/2026-06-15-remove-patches-from-tests.md` (21/8)
- `wiki/pages/2026-06-22-github-pr-description.md` (15/8)
- `wiki/pages/2026-06-22-linear-link-artifact.md` (23/15)
- `wiki/pages/2026-06-25-update-project-version.md` (29/15)
- `wiki/pages/2026-06-25-websocket-to-track-session-statuses.md` (52/11)
- `wiki/pages/2026-07-07-add-context-compaction.md` (32/10)
- `wiki/pages/2026-07-07-project-deploy-script.md` (28/8)
- `wiki/pages/2026-07-15-duplicated-log-messages.md` (68/22)
- `wiki/pages/2026-07-16-fix-empty-build-plan-loop.md` (144/23)
- `wiki/pages/2026-07-16-fix-notification-mark-read.md` (44/14)
- `wiki/pages/2026-07-16-fix-step-status-review-findings.md` (174/72)
- `wiki/pages/2026-07-16-session-history-tokens-null.md` (68/19)
- `wiki/pages/2026-07-16-simplify-session-logging-setup.md` (119/12)
- `wiki/pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md` (15/14)
- `wiki/pages/2026-07-21-awaiting-input-status-for-session.md` (27/8)
- `wiki/pages/2026-07-21-rich-markuperror-and-run-attempts.md` (248/58)
- `wiki/pages/2026-07-22-feature-flag-settings-and-tests.md` (57/16)
- `wiki/pages/2026-07-22-react-frontend-template-warp.md` (195/41)
- `wiki/pages/2026-07-22-warp-theme-review-fixes-and-ops.md` (174/33)
- `wiki/pages/2026-07-23-agents-md-revalidation-and-docs-removal.md` (49/20)
- `wiki/pages/2026-07-23-linear-ticket-email-password-auth.md` (98/40)
- `wiki/pages/2026-07-23-session-history-modal.md` (288/44)
- `wiki/pages/2026-07-23-session-tokens-audit-revalidation.md` (269/46)
- `wiki/pages/2026-07-24-plain-auth-review-followups.md` (202/43)
- `wiki/pages/2026-08-03-auth-hardening-and-deps-bump.md` (146/27)
- `wiki/pages/2026-08-03-check-api-auth-and-credentials.md` (195/29)
- `wiki/pages/2026-08-03-favicon-set-and-react-html.md` (97/27)
- `wiki/pages/2026-08-03-fix-mcp-server-2.0-api.md` (98/17)
- `wiki/pages/2026-08-03-wiki-mcp-tools.md` (90/19)
- `wiki/pages/2026-08-04-fix-resolve-agent-truncated-context.md` (101/53)
- `wiki/pages/2026-08-05-post-build-validation.md` (109/49)
- `wiki/pages/2026-08-05-pr-creation-failure-handler.md` (58/44)
- `wiki/pages/2026-08-06-allowlist-review-fixes.md` (81/31)
- `wiki/pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md` (72/54)
- `wiki/pages/2026-08-07-split-wiki-service-into-subpackage.md` (26/15)
- `wiki/pages/2026-08-09-apply-code-review-findings.md` (70/36)
- `wiki/pages/2026-08-09-apply-pr75-coderabbit-findings.md` (50/26)
- `wiki/pages/2026-08-09-wiki-fixes-and-test-optimization.md` (33/18)
- `wiki/pages/2026-08-10-docker-compose-deploy.md` (72/34)
- `wiki/pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md` (67/58)
- `wiki/pages/2026-08-17-docker-setup-review.md` (283/77)
- `wiki/pages/2026-08-18-categorize-settings-env-vars-by-layer.md` (120/85)
- `wiki/pages/2026-08-18-compose-anchors-refactor.md` (36/21)
- `wiki/pages/2026-08-18-migrate-llm-groq-to-openrouter.md` (99/74)
- `wiki/pages/2026-08-18-test-db-isolation-logging.md` (117/27)
- `wiki/pages/2026-08-19-build-agent-server-error-handler.md` (95/19)
- `wiki/pages/2026-08-19-build-agent-stale-session-deleted-worktree.md` (65/17)
- `wiki/pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md` (139/30)
- `wiki/pages/2026-08-19-wiki-should-use-llm-rename.md` (35/8)
- `wiki/pages/2026-08-19-worker-opencode-home-permissions.md` (43/14)
- `wiki/pages/2026-08-20-fix-allowlist-tests.md` (34/10)
- `wiki/pages/2026-08-20-review-gh-auth-mount-changes.md` (42/11)
- `wiki/pages/2026-08-21-mnt-176-bump-version-error.md` (61/25)
- `wiki/pages/2026-08-24-gh-config-dir-permission-entrypoint.md` (97/19)
- `wiki/pages/2026-08-24-guard-empty-plan-output.md` (49/19)
- `wiki/pages/2026-08-25-loader-styleguide.md` (109/27)
- `wiki/pages/2026-08-25-mnt-181-total-tokens-counter.md` (82/20)
- `wiki/pages/2026-08-25-mnt-187-wiki-pages-not-generated.md` (58/26)
- `wiki/pages/2026-08-28-awaiting-input-workflow-continues-to-review.md` (48/23)
- `wiki/pages/2026-08-28-fix-index-lock-concurrency.md` (26/9)
- `wiki/pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md` (34/23)
- `wiki/pages/2026-08-28-mnt-188-waitlist.md` (90/12)
- `wiki/pages/2026-08-28-mnt-191-ticket-status-not-changed.md` (81/26)
- `wiki/pages/2026-08-31-mnt-192-env-edit-button.md` (68/23)
- `wiki/pages/2026-09-01-mnt-177-research-loop.md` (94/50)
- `wiki/pages/2026-09-02-mobile-template-react-frontend.md` (92/35)
- `wiki/pages/2026-09-02-review-findings-cleanup.md` (94/35)
- `wiki/pages/2026-09-08-docstring-mcp-search.md` (0/67)
- `wiki/pages/2026-09-08-opencode-reasoning-token-zero.md` (23/8)
- `wiki/pages/2026-09-10-mnt-200-update-research-loop.md` (0/78)
- `wiki/pages/2026-09-11-mnt-203-create-related-ticket-for-research.md` (0/65)
- `wiki/pages/2026-09-14-listener-readline-limit-crash.md` (0/89)
- `wiki/pages/2026-09-14-opencode-agent-prompts-hardening.md` (0/130)
- `wiki/pages/2026-09-14-research-plan-artifact.md` (0/62)
- `wiki/pages/2026-09-16-mnt-205-context-environment.md` (166/0)

## Stat

```text
.coderabbit.yaml                                   |   2 -

 .gitattributes                                     |   1 -

 .gitignore                                         |   1 -

 .opencode/agents/build-agent.md                    |  15 +-

 .opencode/agents/merge-agent.md                    |  21 +-

 .opencode/agents/plan-agent.md                     |  26 +-

 .opencode/agents/rebase-agent.md                   |  29 --

 .opencode/agents/research-agent.md                 |  10 +-

 .opencode/agents/resolve-agent.md                  |  14 +-

 .opencode/agents/review-agent.md                   |  18 +-

 .opencode/agents/validate-agent.md                 |  16 +-

 AGENTS.md                                          |  34 +-

 Makefile                                           |  40 ++-

 README.md                                          |   1 -

 configs/bootstrap.sh                               |  16 +

 configs/services/api.service                       |  20 ++

 configs/services/listener.service                  |  20 ++

 configs/services/react.service                     |  21 ++

 configs/services/rq-dashboard.service              |  20 ++

 configs/services/watcher.service                   |  20 ++

 configs/services/worker.service                    |  20 ++

 demetra/library/exceptions.py                      |   6 +-

 demetra/library/models.py                          | 193 ++++++++++-

 demetra/library/tables.py                          |   1 -

 demetra/library/types.py                           |   2 -

 demetra/queries/get_issue_by_title.gql             |   9 -

 demetra/queries/update_issue.gql                   |  10 -

 demetra/services/agents/opencode.py                | 124 ++-----

 demetra/services/daemons/watcher.py                |  33 +-

 demetra/services/linear/__init__.py                |   4 -

 demetra/services/linear/config.py                  |  36 --

 demetra/services/linear/mutations.py               | 171 +---------

 demetra/services/linear/tasks.py                   |   8 +-

 demetra/services/llm/__init__.py                   |   2 -

 demetra/services/llm/config.py                     |  30 --

 demetra/services/llm/factory.py                    |  13 +-

 demetra/services/llm/openrouter.py                 |  49 +--

 demetra/services/persistence/database.py           |  37 +--

 demetra/services/runtime/project.py                |  23 +-

 demetra/services/runtime/utils.py                  |   4 -

 demetra/services/vcs/github.py                     |   4 -

 demetra/services/vcs/merge.py                      |   5 +-

 demetra/services/vcs/rebase.py                     |  13 +-

 demetra/services/wiki/render.py                    |   2 +-

 demetra/settings.py                                |  44 ---

 demetra/tools/docstrings.py                        | 363 ---------------------

 demetra/tools/registry.py                          |  15 +-

 demetra/tools/search.py                            |  19 --

 demetra/tools/wiki.py                              |  60 +++-

 demetra/workflows/build.py                         |  10 +-

 demetra/workflows/cleanup.py                       |   7 +-

 demetra/workflows/failure.py                       |  17 +-

 demetra/workflows/merge.py                         |   6 +-

 demetra/workflows/plan.py                          |  28 +-

 demetra/workflows/rebase.py                        |   6 +-

 demetra/workflows/research.py                      | 174 ++--------

 demetra/workflows/resolve.py                       |   2 +-

 demetra/workflows/review.py                        |   7 +-

 demetra/workflows/review_fixes.py                  |   6 +-

 demetra/workflows/validate.py                      |   7 +-

 docker-compose.yaml                                |   2 -

 main.py                                            |  12 +-

 ...c5d6e7f8_add_sessions_research_report_column.py |  32 --

 pyproject.toml                                     |   3 +-

 react/src/App.css                                  |  15 +-

 react/src/components/LogConsole.tsx                |   2 +-

 react/src/components/SessionArtifacts.test.tsx     |  79 -----

 react/src/components/SessionArtifacts.tsx          |  44 +--

 react/src/components/SessionList.test.tsx          |   5 -

 react/src/index.css                                |   4 -

 react/src/services/api.ts                          |   1 -

 tests/conftest.py                                  |   7 +-

 tests/test_api_coverage.py                         |  24 +-

 tests/test_database.py                             |  50 +--

 tests/test_docstring_tools.py                      | 110 -------

 tests/test_github.py                               |   4 -

 tests/test_linear.py                               | 326 +-----------------

 tests/test_more_coverage.py                        |   6 +-

 tests/test_opencode.py                             |  69 ++--

 tests/test_openrouter.py                           |  20 +-

 tests/test_project.py                              |  28 +-

 tests/test_rebase_service.py                       |   6 +-

 tests/test_session_environment.py                  | 223 +++++++++++++

 tests/test_settings_layers.py                      | 213 +++---------

 tests/test_validate_workflow.py                    |   2 +-

 tests/test_wiki_tools.py                           |   5 +-

 tests/test_workflows.py                            | 277 ++--------------

 uv.lock                                            |  30 +-

 wiki/.obsidian/app.json                            |   3 -

 wiki/.obsidian/appearance.json                     |   1 -

 wiki/.obsidian/core-plugins.json                   |  33 --

 wiki/.obsidian/graph.json                          |  22 --

 wiki/.obsidian/workspace.json                      | 199 -----------

 wiki/.sessions.json                                |   4 +-

 wiki/INDEX.md                                      | 273 ++++++++--------

 wiki/QUESTIONS.md                                  |  11 -

 wiki/audits/2026-09-03-wiki-search-vs-bm25.md      | 176 ----------

 .../2026-06-02-delete-session-button.md            |   0

 .../2026-06-02-plan-loop-resolve-questions.md      |   2 -

 .../2026-06-02-truncate-session-name.md            |   2 -

 .../2026-06-03-context-bloating.md                 |   2 -

 .../2026-06-03-fix-squash-migrations.md            |   0

 .../2026-06-04-review-summarization.md             |   2 -

 .../2026-06-08-max-run-attempts-for-a-ticket.md    |   2 -

 .../2026-06-08-project-environment.md              |   2 -

 .../2026-06-08-session-step-attribute.md           |   2 -

 .../2026-06-09-build-artifacts.md                  |   6 +-

 .../2026-06-09-check-linear-ticket-text.md         |   0

 .../2026-06-09-markdown-renderer.md                |   2 -

 .../2026-06-10-fix-project-creation-timeouts.md    |   0

 wiki/pages/2026-06-15-remove-patches-from-tests.md |  29 +-

 wiki/pages/2026-06-22-github-pr-description.md     |  23 +-

 wiki/pages/2026-06-22-linear-link-artifact.md      |  38 ++-

 wiki/pages/2026-06-25-update-project-version.md    |  44 ++-

 ...26-06-25-websocket-to-track-session-statuses.md |  63 +++-

 wiki/pages/2026-07-07-add-context-compaction.md    |  42 ++-

 wiki/pages/2026-07-07-project-deploy-script.md     |  36 +-

 wiki/pages/2026-07-15-duplicated-log-messages.md   |  90 +++--

 wiki/pages/2026-07-16-fix-empty-build-plan-loop.md | 167 ++++++++--

 .../pages/2026-07-16-fix-notification-mark-read.md |  58 +++-

 .../2026-07-16-fix-step-status-review-findings.md  | 246 ++++++++++----

 .../2026-07-16-session-history-tokens-null.md      |  87 +++--

 .../2026-07-16-simplify-session-logging-setup.md   | 131 +++++++-

 ...7-20-resolve-ansi-color-escape-codes-in-logs.md |  29 +-

 ...2026-07-21-awaiting-input-status-for-session.md |  35 +-

 ...2026-07-21-rich-markuperror-and-run-attempts.md | 306 +++++++++++++----

 .../2026-07-22-feature-flag-settings-and-tests.md  |  73 ++++-

 .../2026-07-22-react-frontend-template-warp.md     | 236 +++++++++++---

 .../2026-07-22-warp-theme-review-fixes-and-ops.md  | 207 ++++++++++--

 ...7-23-agents-md-revalidation-and-docs-removal.md |  69 ++--

 ...2026-07-23-linear-ticket-email-password-auth.md | 138 +++++---

 wiki/pages/2026-07-23-session-history-modal.md     | 332 ++++++++++++++++---

 ...2026-07-23-session-tokens-audit-revalidation.md | 315 +++++++++++++++---

 .../2026-07-24-plain-auth-review-followups.md      | 245 +++++++++++---

 .../2026-08-03-auth-hardening-and-deps-bump.md     | 173 ++++++++--

 .../2026-08-03-check-api-auth-and-credentials.md   | 224 +++++++++++--

 .../pages/2026-08-03-favicon-set-and-react-html.md | 124 +++++--

 wiki/pages/2026-08-03-fix-mcp-server-2.0-api.md    | 115 ++++++-

 wiki/pages/2026-08-03-wiki-mcp-tools.md            | 109 +++++--

 ...26-08-04-fix-resolve-agent-truncated-context.md | 154 ++++++---

 wiki/pages/2026-08-05-post-build-validation.md     | 158 ++++++---

 .../2026-08-05-pr-creation-failure-handler.md      | 102 +++---

 wiki/pages/2026-08-06-allowlist-review-fixes.md    | 112 +++++--

 ...026-08-07-mnt-147-wiki-processes-pr70-review.md | 126 ++++---

 ...026-08-07-split-wiki-service-into-subpackage.md |  41 ++-

 .../pages/2026-08-09-apply-code-review-findings.md | 106 ++++--

 .../2026-08-09-apply-pr75-coderabbit-findings.md   |  76 +++--

 .../2026-08-09-wiki-fixes-and-test-optimization.md |  51 ++-

 wiki/pages/2026-08-10-docker-compose-deploy.md     | 106 ++++--

 ...cess-environment-3-layers-encryption-uv-venv.md | 125 +++----

 wiki/pages/2026-08-17-docker-setup-review.md       | 360 +++++++++++++++-----

 ...-08-18-categorize-settings-env-vars-by-layer.md | 205 +++++++-----

 wiki/pages/2026-08-18-compose-anchors-refactor.md  |  57 ++--

 .../2026-08-18-migrate-llm-groq-to-openrouter.md   | 173 +++++-----

 wiki/pages/2026-08-18-test-db-isolation-logging.md | 144 ++++++--

 .../2026-08-19-build-agent-server-error-handler.md | 114 +++++--

 ...9-build-agent-stale-session-deleted-worktree.md |  82 ++++-

 ...-linear-services-and-review-failure-handling.md | 169 ++++++++--

 .../pages/2026-08-19-wiki-should-use-llm-rename.md |  43 ++-

 .../2026-08-19-worker-opencode-home-permissions.md |  57 +++-

 wiki/pages/2026-08-20-fix-allowlist-tests.md       |  44 ++-

 .../2026-08-20-review-gh-auth-mount-changes.md     |  53 ++-

 .../pages/2026-08-21-mnt-176-bump-version-error.md |  86 +++--

 ...26-08-24-gh-config-dir-permission-entrypoint.md | 116 +++++--

 wiki/pages/2026-08-24-guard-empty-plan-output.md   |  68 ++--

 wiki/pages/2026-08-25-loader-styleguide.md         | 136 ++++++--

 .../2026-08-25-mnt-181-total-tokens-counter.md     | 102 ++++--

 .../2026-08-25-mnt-187-wiki-pages-not-generated.md |  84 +++--

 ...-awaiting-input-workflow-continues-to-review.md |  71 ++--

 .../pages/2026-08-28-fix-index-lock-concurrency.md |  35 +-

 ...8-28-mnt-177-workflow-blocked-openrouter-403.md |  57 ++--

 wiki/pages/2026-08-28-mnt-188-waitlist.md          | 102 +++++-

 ...2026-08-28-mnt-191-ticket-status-not-changed.md | 107 ++++--

 wiki/pages/2026-08-31-mnt-192-env-edit-button.md   |  91 ++++--

 wiki/pages/2026-09-01-mnt-177-research-loop.md     | 144 +++++---

 .../2026-09-02-mobile-template-react-frontend.md   | 127 +++++--

 wiki/pages/2026-09-02-review-findings-cleanup.md   | 129 ++++++--

 wiki/pages/2026-09-08-docstring-mcp-search.md      |  67 ----

 .../2026-09-08-opencode-reasoning-token-zero.md    |  31 +-

 .../2026-09-10-mnt-200-update-research-loop.md     |  78 -----

 ...1-mnt-203-create-related-ticket-for-research.md |  65 ----

 .../2026-09-14-listener-readline-limit-crash.md    |  89 -----

 .../2026-09-14-opencode-agent-prompts-hardening.md | 130 --------

 wiki/pages/2026-09-14-research-plan-artifact.md    |  62 ----

 .../2026-09-16-mnt-205-context-environment.md      | 166 ++++++++++

 185 files changed, 7381 insertions(+), 5462 deletions(-)
```

## Build plan

## Implementation Plan
The implementation plan involves standardizing the methods for resolving agent models, Linear settings, and OpenRouter settings by introducing a single `SessionEnvironment` resolver. This resolver will be exposed as the `environment` property on the `Context` object, allowing all workflow steps and helpers to read from the same place.

### Key Technical Decisions
- Introduce a `SessionEnvironment` resolver in `demetra/library/models.py` that looks up workflow environment keys through three layers: project environment, user-shared environment, and settings defaults.
- Raise an `EnvironmentError` when a key is not found in any of the layers.
- Expose the `SessionEnvironment` resolver as the `environment` property on the `Context` object.
- Delete duplicate resolvers (`…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f55832b3effeWJy0LClcVV2V83`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-205/revise-merged-environment
