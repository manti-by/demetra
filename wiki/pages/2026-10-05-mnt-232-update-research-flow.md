---
title: 'MNT-232: Update research flow'
date: '2026-10-06'
type: implementation
status: resolved
session_id: ses_ef2314203ffe3rEkhgo1cOltPV
services: [.coderabbit, .dockerignore, .env.docker, .gitattributes, .gitignore, build-agent,
  merge-agent, plan-agent, rebase-agent, research-agent, resolve-agent, review-agent,
  validate-agent, package-lock, SKILL, AGENTS, Dockerfile, Makefile, README, bootstrap,
  api, listener, react, rq-dashboard, watcher, worker, library, queries, agents/opencode,
  daemons/listener, daemons/watcher, linear/__init__, linear/config, linear/mutations,
  linear/tasks, llm/__init__, llm/config, llm/factory, llm/groq, llm/openrouter, persistence/database,
  runtime/project, runtime/utils, vcs/github, vcs/merge, vcs/rebase, wiki/__init__,
  wiki/render, settings, tools, workflows, docker-compose, main, env, a3b4c5d6e7f8_add_sessions_research_ticket_id_column,
  opencode, pyproject, App, LogConsole.test, LogConsole, SessionArtifacts.test, SessionArtifacts,
  SessionHistory.test, SessionHistory, SessionList.test, index, conftest, test_api,
  test_api_coverage, test_database, test_docker_compose, test_docstring_tools, test_git,
  test_git_service, test_github, test_groq, test_linear, test_listener, test_more_coverage,
  test_more_edge_cases, test_opencode, test_openrouter, test_project, test_rebase_service,
  test_session_environment, test_settings, test_settings_layers, test_validate_workflow,
  test_wiki, test_wiki_tools, test_workflows, uv, app, appearance, core-plugins, graph,
  workspace, .sessions, INDEX, QUESTIONS, 2026-03-11-separate-linear-comments, 2026-03-11-task-plan-summarization,
  2026-03-13-sqlalchemy-core-support, 2026-03-31-project-model-and-space, 2026-04-02-link-user-tasks-sessions,
  2026-05-22-task-title-session-listing, 2026-05-25-async-review, 2026-05-25-remove-ticket-api,
  2026-06-01-add-mcp-server, 2026-06-01-refactor-api, 2026-06-01-refactor-frontend-app,
  2026-09-03-wiki-search-vs-bm25, 2026-06-02-plan-loop-resolve-questions, 2026-06-02-truncate-session-name,
  2026-06-03-context-bloating, 2026-06-04-review-summarization, 2026-06-08-max-run-attempts-for-a-ticket,
  2026-06-08-project-environment, 2026-06-08-session-step-attribute, 2026-06-09-build-artifacts,
  2026-06-09-markdown-renderer, 2026-06-15-remove-patches-from-tests, 2026-06-22-github-pr-description,
  2026-06-22-linear-link-artifact, 2026-06-25-update-project-version, 2026-06-25-websocket-to-track-session-statuses,
  2026-07-07-add-context-compaction, 2026-07-07-project-deploy-script, 2026-07-15-duplicated-log-messages,
  2026-07-16-fix-empty-build-plan-loop, 2026-07-16-fix-notification-mark-read, 2026-07-16-fix-step-status-review-findings,
  2026-07-16-session-history-tokens-null, 2026-07-16-simplify-session-logging-setup,
  2026-07-20-resolve-ansi-color-escape-codes-in-logs, 2026-07-21-awaiting-input-status-for-session,
  2026-07-21-rich-markuperror-and-run-attempts, 2026-07-22-feature-flag-settings-and-tests,
  2026-07-22-react-frontend-template-warp, 2026-07-22-warp-theme-review-fixes-and-ops,
  2026-07-23-agents-md-revalidation-and-docs-removal, 2026-07-23-linear-ticket-email-password-auth,
  2026-07-23-session-history-modal, 2026-07-23-session-tokens-audit-revalidation,
  2026-07-24-plain-auth-review-followups, 2026-08-03-agents-md-and-wiki-consistency,
  2026-08-03-auth-hardening-and-deps-bump, 2026-08-03-check-api-auth-and-credentials,
  2026-08-03-favicon-set-and-react-html, 2026-08-03-fix-mcp-server-2.0-api, 2026-08-03-wiki-mcp-tools,
  2026-08-04-fix-resolve-agent-truncated-context, 2026-08-05-post-build-validation,
  2026-08-05-pr-creation-failure-handler, 2026-08-06-allowlist-review-fixes, 2026-08-07-mnt-147-wiki-processes-pr70-review,
  2026-08-07-split-wiki-service-into-subpackage, 2026-08-09-apply-code-review-findings,
  2026-08-09-apply-pr75-coderabbit-findings, 2026-08-09-wiki-fixes-and-test-optimization,
  2026-08-10-docker-compose-deploy, 2026-08-10-process-environment-3-layers-encryption-uv-venv,
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
  2026-09-16-mnt-205-revise-merged-environment, 2026-09-18-dockerfile-opencode-agents-skills,
  2026-09-24-mnt-219-session-log-autoscroll, 2026-09-27-mnt-225-add-copy-button, 2026-09-28-compose-langsmith-host-env,
  2026-09-30-mnt-228-intermediate-history-states, 2026-10-05-mnt-232-update-research-flow]
branch: mnt-232-update-research-flow
tickets: [MNT-232]
tags: [wiki, bug, backend]
related: [2026-09-01-mnt-177-research-loop.md]
---
# MNT-232: Update research flow

## TL;DR

The research flow has been updated to link new tickets with reports to the original session ticket and move the original ticket to the review column. The session state is now set to 'Researched' after research is completed. All tests have passed, and a new wiki page has been added to document the change.

---

## Overview

The implementation involved updating the research flow final state, adding a new IssueRelationCreate GraphQL mutation, and rewriting the run_research_step function to create, link, and review tickets. Key changes were made to demetra/workflows/research.py, demetra/services/linear/mutations.py, and demetra/library/models.py, with new files added including demetra/queries/create_issue_relation.gql and wiki/pages/2026-10-05-mnt-232-update-research-flow.md.

## Changed files

- `.coderabbit.yaml` (0/2)
- `.dockerignore` (0/4)
- `.env.docker.example` (3/6)
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
- `.opencode/package-lock.json` (8/8)
- `.opencode/skills/fix-review-findings/SKILL.md` (32/0)
- `.opencode/skills/release-name/SKILL.md` (49/0)
- `.opencode/skills/release-notes/SKILL.md` (81/0)
- `.opencode/skills/wiki-agents-file/SKILL.md` (70/0)
- `.opencode/skills/wiki-archive/SKILL.md` (198/0)
- `.opencode/skills/wiki-consistency/SKILL.md` (74/0)
- `.opencode/skills/wiki-dedup/SKILL.md` (79/0)
- `.opencode/skills/{wiki-sync => wiki-update}/SKILL.md` (0/0)
- `AGENTS.md` (24/27)
- `Dockerfile` (1/11)
- `Makefile` (25/15)
- `README.md` (0/1)
- `configs/bootstrap.sh` (16/0)
- `configs/services/api.service` (20/0)
- `configs/services/listener.service` (20/0)
- `configs/services/react.service` (21/0)
- `configs/services/rq-dashboard.service` (20/0)
- `configs/services/watcher.service` (20/0)
- `configs/services/worker.service` (20/0)
- `demetra/library/constants.py` (0/31)
- `demetra/library/exceptions.py` (0/8)
- `demetra/library/models.py` (3/192)
- `demetra/library/tables.py` (1/1)
- `demetra/library/types.py` (5/10)
- `demetra/queries/create_issue_relation.gql` (17/0)
- `demetra/queries/get_issue_by_title.gql` (0/9)
- `demetra/queries/update_issue.gql` (0/10)
- `demetra/services/agents/opencode.py` (61/61)
- `demetra/services/daemons/listener.py` (3/4)
- `demetra/services/daemons/watcher.py` (10/38)
- `demetra/services/linear/__init__.py` (4/2)
- `demetra/services/linear/config.py` (36/0)
- `demetra/services/linear/mutations.py` (46/177)
- `demetra/services/linear/tasks.py` (2/6)
- `demetra/services/llm/__init__.py` (2/0)
- `demetra/services/llm/config.py` (30/0)
- `demetra/services/llm/factory.py` (6/7)
- `demetra/services/llm/groq.py` (247/0)
- `demetra/services/llm/openrouter.py` (82/83)
- `demetra/services/persistence/database.py` (33/55)
- `demetra/services/runtime/project.py` (7/20)
- `demetra/services/runtime/utils.py` (0/4)
- `demetra/services/vcs/github.py` (0/4)
- `demetra/services/vcs/merge.py` (6/7)
- `demetra/services/vcs/rebase.py` (10/11)
- `demetra/services/wiki/__init__.py` (1/0)
- `demetra/services/wiki/render.py` (1/1)
- `demetra/settings.py` (22/38)
- `demetra/tools/database.py` (7/7)
- `demetra/tools/docstrings.py` (0/363)
- `demetra/tools/registry.py` (4/11)
- `demetra/tools/search.py` (0/20)
- `demetra/tools/wiki.py` (50/10)
- `demetra/workflows/build.py` (17/17)
- `demetra/workflows/cleanup.py` (6/5)
- `demetra/workflows/failure.py` (6/11)
- `demetra/workflows/lint.py` (6/7)
- `demetra/workflows/merge.py` (2/4)
- `demetra/workflows/plan.py` (13/21)
- `demetra/workflows/rebase.py` (2/4)
- `demetra/workflows/research.py` (63/154)
- `demetra/workflows/resolve.py` (1/1)
- `demetra/workflows/review.py` (3/4)
- `demetra/workflows/review_fixes.py` (2/4)
- `demetra/workflows/validate.py` (3/4)
- `docker-compose.yaml` (0/6)
- `main.py` (8/8)
- `migrations/env.py` (6/6)
- `migrations/versions/{a3b4c5d6e7f8_add_sessions_research_report_column.py => a3b4c5d6e7f8_add_sessions_research_ticket_id_column.py}` (4/4)
- `opencode.json` (32/0)
- `pyproject.toml` (2/2)
- `react/src/App.css` (1/14)
- `react/src/components/LogConsole.test.tsx` (1/72)
- `react/src/components/LogConsole.tsx` (2/2)
- `react/src/components/SessionArtifacts.test.tsx` (1/169)
- `react/src/components/SessionArtifacts.tsx` (2/84)
- `react/src/components/SessionHistory.test.tsx` (0/19)
- `react/src/components/SessionHistory.tsx` (13/7)
- `react/src/components/SessionList.test.tsx` (0/5)
- `react/src/index.css` (0/4)
- `react/src/services/api.ts` (0/1)
- `tests/conftest.py` (20/13)
- `tests/test_api.py` (13/22)
- `tests/test_api_coverage.py` (12/12)
- `tests/test_database.py` (1372/39)
- `tests/test_docker_compose.py` (0/49)
- `tests/test_docstring_tools.py` (0/110)
- `tests/test_git.py` (46/0)
- `tests/test_git_service.py` (220/0)
- `tests/test_github.py` (0/4)
- `tests/test_groq.py` (183/0)
- `tests/test_linear.py` (44/342)
- `tests/test_listener.py` (2/2)
- `tests/test_more_coverage.py` (2/31)
- `tests/test_more_edge_cases.py` (100/0)
- `tests/test_opencode.py` (128/88)
- `tests/test_openrouter.py` (10/10)
- `tests/test_project.py` (4/24)
- `tests/test_rebase_service.py` (3/3)
- `tests/test_session_environment.py` (0/223)
- `tests/test_settings.py` (29/45)
- `tests/test_settings_layers.py` (171/42)
- `tests/test_validate_workflow.py` (1/1)
- `tests/test_wiki.py` (4/3)
- `tests/test_wiki_tools.py` (2/7)
- `tests/test_workflows.py` (140/411)
- `uv.lock` (34/28)
- `wiki/.obsidian/app.json` (0/3)
- `wiki/.obsidian/appearance.json` (0/1)
- `wiki/.obsidian/core-plugins.json` (0/33)
- `wiki/.obsidian/graph.json` (0/22)
- `wiki/.obsidian/workspace.json` (0/199)
- `wiki/.sessions.json` (1/5)
- `wiki/INDEX.md` (138/176)
- `wiki/QUESTIONS.md` (0/11)
- `wiki/archive/2026-03-11-separate-linear-comments.md` (8/19)
- `wiki/archive/2026-03-11-task-plan-summarization.md` (8/21)
- `wiki/archive/2026-03-13-sqlalchemy-core-support.md` (7/17)
- `wiki/{pages => archive}/2026-03-31-project-model-and-space.md` (7/20)
- `wiki/{pages => archive}/2026-04-02-link-user-tasks-sessions.md` (7/20)
- `wiki/{pages => archive}/2026-05-22-task-title-session-listing.md` (6/21)
- `wiki/{pages => archive}/2026-05-25-async-review.md` (3/3)
- `wiki/{pages => archive}/2026-05-25-remove-ticket-api.md` (1/1)
- `wiki/{pages => archive}/2026-06-01-add-mcp-server.md` (0/0)
- `wiki/{pages => archive}/2026-06-01-refactor-api.md` (6/15)
- `wiki/{pages => archive}/2026-06-01-refactor-frontend-app.md` (6/15)
- `wiki/audits/2026-09-03-wiki-search-vs-bm25.md` (0/176)
- `wiki/pages/2026-06-02-plan-loop-resolve-questions.md` (6/19)
- `wiki/pages/2026-06-02-truncate-session-name.md` (6/17)
- `wiki/pages/2026-06-03-context-bloating.md` (8/22)
- `wiki/pages/2026-06-04-review-summarization.md` (1/3)
- `wiki/pages/2026-06-08-max-run-attempts-for-a-ticket.md` (0/2)
- `wiki/pages/2026-06-08-project-environment.md` (7/24)
- `wiki/pages/2026-06-08-session-step-attribute.md` (0/2)
- `wiki/pages/2026-06-09-build-artifacts.md` (8/23)
- `wiki/pages/2026-06-09-markdown-renderer.md` (8/20)
- `wiki/pages/2026-06-15-remove-patches-from-tests.md` (21/8)
- `wiki/pages/2026-06-22-github-pr-description.md` (16/13)
- `wiki/pages/2026-06-22-linear-link-artifact.md` (23/19)
- `wiki/pages/2026-06-25-update-project-version.md` (29/20)
- `wiki/pages/2026-06-25-websocket-to-track-session-statuses.md` (52/15)
- `wiki/pages/2026-07-07-add-context-compaction.md` (33/15)
- `wiki/pages/2026-07-07-project-deploy-script.md` (30/13)
- `wiki/pages/2026-07-15-duplicated-log-messages.md` (69/26)
- `wiki/pages/2026-07-16-fix-empty-build-plan-loop.md` (144/28)
- `wiki/pages/2026-07-16-fix-notification-mark-read.md` (44/14)
- `wiki/pages/2026-07-16-fix-step-status-review-findings.md` (174/72)
- `wiki/pages/2026-07-16-session-history-tokens-null.md` (68/19)
- `wiki/pages/2026-07-16-simplify-session-logging-setup.md` (120/17)
- `wiki/pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md` (15/14)
- `wiki/pages/2026-07-21-awaiting-input-status-for-session.md` (28/13)
- `wiki/pages/2026-07-21-rich-markuperror-and-run-attempts.md` (250/64)
- `wiki/pages/2026-07-22-feature-flag-settings-and-tests.md` (59/21)
- `wiki/pages/2026-07-22-react-frontend-template-warp.md` (195/47)
- `wiki/pages/2026-07-22-warp-theme-review-fixes-and-ops.md` (174/38)
- `wiki/pages/2026-07-23-agents-md-revalidation-and-docs-removal.md` (50/24)
- `wiki/pages/2026-07-23-linear-ticket-email-password-auth.md` (99/45)
- `wiki/pages/2026-07-23-session-history-modal.md` (289/50)
- `wiki/pages/2026-07-23-session-tokens-audit-revalidation.md` (269/50)
- `wiki/pages/2026-07-24-plain-auth-review-followups.md` (203/51)
- `wiki/pages/2026-08-03-agents-md-and-wiki-consistency.md` (2/11)
- `wiki/pages/2026-08-03-auth-hardening-and-deps-bump.md` (146/31)
- `wiki/pages/2026-08-03-check-api-auth-and-credentials.md` (196/37)
- `wiki/pages/2026-08-03-favicon-set-and-react-html.md` (98/31)
- `wiki/pages/2026-08-03-fix-mcp-server-2.0-api.md` (98/21)
- `wiki/pages/2026-08-03-wiki-mcp-tools.md` (90/23)
- `wiki/pages/2026-08-04-fix-resolve-agent-truncated-context.md` (101/53)
- `wiki/pages/2026-08-05-post-build-validation.md` (109/49)
- `wiki/pages/2026-08-05-pr-creation-failure-handler.md` (52/44)
- `wiki/pages/2026-08-06-allowlist-review-fixes.md` (82/38)
- `wiki/pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md` (72/54)
- `wiki/pages/2026-08-07-split-wiki-service-into-subpackage.md` (27/22)
- `wiki/pages/2026-08-09-apply-code-review-findings.md` (71/43)
- `wiki/pages/2026-08-09-apply-pr75-coderabbit-findings.md` (50/30)
- `wiki/pages/2026-08-09-wiki-fixes-and-test-optimization.md` (34/24)
- `wiki/pages/2026-08-10-docker-compose-deploy.md` (72/40)
- `wiki/pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md` (60/58)
- `wiki/pages/2026-08-17-docker-setup-review.md` (283/83)
- `wiki/pages/2026-08-18-categorize-settings-env-vars-by-layer.md` (114/85)
- `wiki/pages/2026-08-18-compose-anchors-refactor.md` (37/26)
- `wiki/pages/2026-08-18-migrate-llm-groq-to-openrouter.md` (99/73)
- `wiki/pages/2026-08-18-test-db-isolation-logging.md` (118/33)
- `wiki/pages/2026-08-19-build-agent-server-error-handler.md` (96/26)
- `wiki/pages/2026-08-19-build-agent-stale-session-deleted-worktree.md` (60/29)
- `wiki/pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md` (134/44)
- `wiki/pages/2026-08-19-wiki-should-use-llm-rename.md` (36/13)
- `wiki/pages/2026-08-19-worker-opencode-home-permissions.md` (44/21)
- `wiki/pages/2026-08-20-fix-allowlist-tests.md` (35/15)
- `wiki/pages/2026-08-20-review-gh-auth-mount-changes.md` (43/17)
- `wiki/pages/2026-08-21-mnt-176-bump-version-error.md` (61/29)
- `wiki/pages/2026-08-24-gh-config-dir-permission-entrypoint.md` (98/25)
- `wiki/pages/2026-08-24-guard-empty-plan-output.md` (49/25)
- `wiki/pages/2026-08-25-loader-styleguide.md` (110/33)
- `wiki/pages/2026-08-25-mnt-181-total-tokens-counter.md` (83/28)
- `wiki/pages/2026-08-25-mnt-187-wiki-pages-not-generated.md` (59/32)
- `wiki/pages/2026-08-28-awaiting-input-workflow-continues-to-review.md` (49/31)
- `wiki/pages/2026-08-28-fix-index-lock-concurrency.md` (27/14)
- `wiki/pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md` (29/27)
- `wiki/pages/2026-08-28-mnt-188-waitlist.md` (91/17)
- `wiki/pages/2026-08-28-mnt-191-ticket-status-not-changed.md` (76/38)
- `wiki/pages/2026-08-31-mnt-192-env-edit-button.md` (69/27)
- `wiki/pages/2026-09-01-mnt-177-research-loop.md` (88/50)
- `wiki/pages/2026-09-02-mobile-template-react-frontend.md` (92/41)
- `wiki/pages/2026-09-02-review-findings-cleanup.md` (95/42)
- `wiki/pages/2026-09-08-docstring-mcp-search.md` (0/72)
- `wiki/pages/2026-09-08-opencode-reasoning-token-zero.md` (24/12)
- `wiki/pages/2026-09-10-mnt-200-update-research-loop.md` (0/78)
- `wiki/pages/2026-09-11-mnt-203-create-related-ticket-for-research.md` (0/65)
- `wiki/pages/2026-09-14-listener-readline-limit-crash.md` (0/92)
- `wiki/pages/2026-09-14-opencode-agent-prompts-hardening.md` (0/134)
- `wiki/pages/2026-09-14-research-plan-artifact.md` (0/65)
- `wiki/pages/2026-09-16-mnt-205-revise-merged-environment.md` (0/618)
- `wiki/pages/2026-09-18-dockerfile-opencode-agents-skills.md` (0/97)
- `wiki/pages/2026-09-24-mnt-219-session-log-autoscroll.md` (0/688)
- `wiki/pages/2026-09-27-mnt-225-add-copy-button.md` (0/74)
- `wiki/pages/2026-09-28-compose-langsmith-host-env.md` (0/227)
- `wiki/pages/2026-09-30-mnt-228-intermediate-history-states.md` (0/101)
- `wiki/pages/2026-10-05-mnt-232-update-research-flow.md` (192/0)

## Stat

```text
.coderabbit.yaml                                   |    2 -

 .dockerignore                                      |    4 -

 .env.docker.example                                |    9 +-

 .gitattributes                                     |    1 -

 .gitignore                                         |    1 -

 .opencode/agents/build-agent.md                    |   15 +-

 .opencode/agents/merge-agent.md                    |   21 +-

 .opencode/agents/plan-agent.md                     |   26 +-

 .opencode/agents/rebase-agent.md                   |   29 -

 .opencode/agents/research-agent.md                 |   10 +-

 .opencode/agents/resolve-agent.md                  |   14 +-

 .opencode/agents/review-agent.md                   |   18 +-

 .opencode/agents/validate-agent.md                 |   16 +-

 .opencode/package-lock.json                        |   16 +-

 .opencode/skills/fix-review-findings/SKILL.md      |   32 +

 .opencode/skills/release-name/SKILL.md             |   49 +

 .opencode/skills/release-notes/SKILL.md            |   81 ++

 .opencode/skills/wiki-agents-file/SKILL.md         |   70 +

 .opencode/skills/wiki-archive/SKILL.md             |  198 +++

 .opencode/skills/wiki-consistency/SKILL.md         |   74 +

 .opencode/skills/wiki-dedup/SKILL.md               |   79 ++

 .../skills/{wiki-sync => wiki-update}/SKILL.md     |    0

 AGENTS.md                                          |   51 +-

 Dockerfile                                         |   12 +-

 Makefile                                           |   40 +-

 README.md                                          |    1 -

 configs/bootstrap.sh                               |   16 +

 configs/services/api.service                       |   20 +

 configs/services/listener.service                  |   20 +

 configs/services/react.service                     |   21 +

 configs/services/rq-dashboard.service              |   20 +

 configs/services/watcher.service                   |   20 +

 configs/services/worker.service                    |   20 +

 demetra/library/constants.py                       |   31 -

 demetra/library/exceptions.py                      |    8 -

 demetra/library/models.py                          |  195 +--

 demetra/library/tables.py                          |    2 +-

 demetra/library/types.py                           |   15 +-

 demetra/queries/create_issue_relation.gql          |   17 +

 demetra/queries/get_issue_by_title.gql             |    9 -

 demetra/queries/update_issue.gql                   |   10 -

 demetra/services/agents/opencode.py                |  122 +-

 demetra/services/daemons/listener.py               |    7 +-

 demetra/services/daemons/watcher.py                |   48 +-

 demetra/services/linear/__init__.py                |    6 +-

 demetra/services/linear/config.py                  |   36 +

 demetra/services/linear/mutations.py               |  223 +---

 demetra/services/linear/tasks.py                   |    8 +-

 demetra/services/llm/__init__.py                   |    2 +

 demetra/services/llm/config.py                     |   30 +

 demetra/services/llm/factory.py                    |   13 +-

 demetra/services/llm/groq.py                       |  247 ++++

 demetra/services/llm/openrouter.py                 |  165 ++-

 demetra/services/persistence/database.py           |   88 +-

 demetra/services/runtime/project.py                |   27 +-

 demetra/services/runtime/utils.py                  |    4 -

 demetra/services/vcs/github.py                     |    4 -

 demetra/services/vcs/merge.py                      |   13 +-

 demetra/services/vcs/rebase.py                     |   21 +-

 demetra/services/wiki/__init__.py                  |    1 +

 demetra/services/wiki/render.py                    |    2 +-

 demetra/settings.py                                |   60 +-

 demetra/tools/database.py                          |   14 +-

 demetra/tools/docstrings.py                        |  363 -----

 demetra/tools/registry.py                          |   15 +-

 demetra/tools/search.py                            |   20 -

 demetra/tools/wiki.py                              |   60 +-

 demetra/workflows/build.py                         |   34 +-

 demetra/workflows/cleanup.py                       |   11 +-

 demetra/workflows/failure.py                       |   17 +-

 demetra/workflows/lint.py                          |   13 +-

 demetra/workflows/merge.py                         |    6 +-

 demetra/workflows/plan.py                          |   34 +-

 demetra/workflows/rebase.py                        |    6 +-

 demetra/workflows/research.py                      |  217 +--

 demetra/workflows/resolve.py                       |    2 +-

 demetra/workflows/review.py                        |    7 +-

 demetra/workflows/review_fixes.py                  |    6 +-

 demetra/workflows/validate.py                      |    7 +-

 docker-compose.yaml                                |    6 -

 main.py                                            |   16 +-

 migrations/env.py                                  |   12 +-

 ...e7f8_add_sessions_research_ticket_id_column.py} |    8 +-

 opencode.json                                      |   32 +

 pyproject.toml                                     |    4 +-

 react/src/App.css                                  |   15 +-

 react/src/components/LogConsole.test.tsx           |   73 +-

 react/src/components/LogConsole.tsx                |    4 +-

 react/src/components/SessionArtifacts.test.tsx     |  170 +--

 react/src/components/SessionArtifacts.tsx          |   86 +-

 react/src/components/SessionHistory.test.tsx       |   19 -

 react/src/components/SessionHistory.tsx            |   20 +-

 react/src/components/SessionList.test.tsx          |    5 -

 react/src/index.css                                |    4 -

 react/src/services/api.ts                          |    1 -

 tests/conftest.py                                  |   33 +-

 tests/test_api.py                                  |   35 +-

 tests/test_api_coverage.py                         |   24 +-

 tests/test_database.py                             | 1411 +++++++++++++++++++-

 tests/test_docker_compose.py                       |   49 -

 tests/test_docstring_tools.py                      |  110 --

 tests/test_git.py                                  |   46 +

 tests/test_git_service.py                          |  220 +++

 tests/test_github.py                               |    4 -

 tests/test_groq.py                                 |  183 +++

 tests/test_linear.py                               |  386 +-----

 tests/test_listener.py                             |    4 +-

 tests/test_more_coverage.py                        |   33 +-

 tests/test_more_edge_cases.py                      |  100 ++

 tests/test_opencode.py                             |  216 +--

 tests/test_openrouter.py                           |   20 +-

 tests/test_project.py                              |   28 +-

 tests/test_rebase_service.py                       |    6 +-

 tests/test_session_environment.py                  |  223 ----

 tests/test_settings.py                             |   74 +-

 tests/test_settings_layers.py                      |  213 ++-

 tests/test_validate_workflow.py                    |    2 +-

 tests/test_wiki.py                                 |    7 +-

 tests/test_wiki_tools.py                           |    9 +-

 tests/test_workflows.py                            |  551 ++------

 uv.lock                                            |   62 +-

 wiki/.obsidian/app.json                            |    3 -

 wiki/.obsidian/appearance.json                     |    1 -

 wiki/.obsidian/core-plugins.json                   |   33 -

 wiki/.obsidian/graph.json                          |   22 -

 wiki/.obsidian/workspace.json                      |  199 ---

 wiki/.sessions.json                                |    6 +-

 wiki/INDEX.md                                      |  314 ++---

 wiki/QUESTIONS.md                                  |   11 -

 .../archive/2026-03-11-separate-linear-comments.md |   27 +-

 wiki/archive/2026-03-11-task-plan-summarization.md |   29 +-

 wiki/archive/2026-03-13-sqlalchemy-core-support.md |   24 +-

 .../2026-03-31-project-model-and-space.md          |   27 +-

 .../2026-04-02-link-user-tasks-sessions.md         |   27 +-

 .../2026-05-22-task-title-session-listing.md       |   27 +-

 wiki/{pages => archive}/2026-05-25-async-review.md |    6 +-

 .../2026-05-25-remove-ticket-api.md                |    2 +-

 .../2026-06-01-add-mcp-server.md                   |    0

 wiki/{pages => archive}/2026-06-01-refactor-api.md |   21 +-

 .../2026-06-01-refactor-frontend-app.md            |   21 +-

 wiki/audits/2026-09-03-wiki-search-vs-bm25.md      |  176 ---

 .../2026-06-02-plan-loop-resolve-questions.md      |   25 +-

 wiki/pages/2026-06-02-truncate-session-name.md     |   23 +-

 wiki/pages/2026-06-03-context-bloating.md          |   30 +-

 wiki/pages/2026-06-04-review-summarization.md      |    4 +-

 .../2026-06-08-max-run-attempts-for-a-ticket.md    |    2 -

 wiki/pages/2026-06-08-project-environment.md       |   31 +-

 wiki/pages/2026-06-08-session-step-attribute.md    |    2 -

 wiki/pages/2026-06-09-build-artifacts.md           |   31 +-

 wiki/pages/2026-06-09-markdown-renderer.md         |   28 +-

 wiki/pages/2026-06-15-remove-patches-from-tests.md |   29 +-

 wiki/pages/2026-06-22-github-pr-description.md     |   29 +-

 wiki/pages/2026-06-22-linear-link-artifact.md      |   42 +-

 wiki/pages/2026-06-25-update-project-version.md    |   49 +-

 ...26-06-25-websocket-to-track-session-statuses.md |   67 +-

 wiki/pages/2026-07-07-add-context-compaction.md    |   48 +-

 wiki/pages/2026-07-07-project-deploy-script.md     |   43 +-

 wiki/pages/2026-07-15-duplicated-log-messages.md   |   95 +-

 wiki/pages/2026-07-16-fix-empty-build-plan-loop.md |  172 ++-

 .../pages/2026-07-16-fix-notification-mark-read.md |   58 +-

 .../2026-07-16-fix-step-status-review-findings.md  |  246 +++-

 .../2026-07-16-session-history-tokens-null.md      |   87 +-

 .../2026-07-16-simplify-session-logging-setup.md   |  137 +-

 ...7-20-resolve-ansi-color-escape-codes-in-logs.md |   29 +-

 ...2026-07-21-awaiting-input-status-for-session.md |   41 +-

 ...2026-07-21-rich-markuperror-and-run-attempts.md |  314 ++++-

 .../2026-07-22-feature-flag-settings-and-tests.md  |   80 +-

 .../2026-07-22-react-frontend-template-warp.md     |  242 +++-

 .../2026-07-22-warp-theme-review-fixes-and-ops.md  |  212 ++-

 ...7-23-agents-md-revalidation-and-docs-removal.md |   74 +-

 ...2026-07-23-linear-ticket-email-password-auth.md |  144 +-

 wiki/pages/2026-07-23-session-history-modal.md     |  339 ++++-

 ...2026-07-23-session-tokens-audit-revalidation.md |  319 ++++-

 .../2026-07-24-plain-auth-review-followups.md      |  254 +++-

 .../2026-08-03-agents-md-and-wiki-consistency.md   |   13 +-

 .../2026-08-03-auth-hardening-and-deps-bump.md     |  177 ++-

 .../2026-08-03-check-api-auth-and-credentials.md   |  233 +++-

 .../pages/2026-08-03-favicon-set-and-react-html.md |  129 +-

 wiki/pages/2026-08-03-fix-mcp-server-2.0-api.md    |  119 +-

 wiki/pages/2026-08-03-wiki-mcp-tools.md            |  113 +-

 ...26-08-04-fix-resolve-agent-truncated-context.md |  154 ++-

 wiki/pages/2026-08-05-post-build-validation.md     |  158 ++-

 .../2026-08-05-pr-creation-failure-handler.md      |   96 +-

 wiki/pages/2026-08-06-allowlist-review-fixes.md    |  120 +-

 ...026-08-07-mnt-147-wiki-processes-pr70-review.md |  126 +-

 ...026-08-07-split-wiki-service-into-subpackage.md |   49 +-

 .../pages/2026-08-09-apply-code-review-findings.md |  114 +-

 .../2026-08-09-apply-pr75-coderabbit-findings.md   |   80 +-

 .../2026-08-09-wiki-fixes-and-test-optimization.md |   58 +-

 wiki/pages/2026-08-10-docker-compose-deploy.md     |  112 +-

 ...cess-environment-3-layers-encryption-uv-venv.md |  118 +-

 wiki/pages/2026-08-17-docker-setup-review.md       |  366 +++--

 ...-08-18-categorize-settings-env-vars-by-layer.md |  199 +--

 wiki/pages/2026-08-18-compose-anchors-refactor.md  |   63 +-

 .../2026-08-18-migrate-llm-groq-to-openrouter.md   |  172 ++-

 wiki/pages/2026-08-18-test-db-isolation-logging.md |  151 ++-

 .../2026-08-19-build-agent-server-error-handler.md |  122 +-

 ...9-build-agent-stale-session-deleted-worktree.md |   89 +-

 ...-linear-services-and-review-failure-handling.md |  178 ++-

 .../pages/2026-08-19-wiki-should-use-llm-rename.md |   49 +-

 .../2026-08-19-worker-opencode-home-permissions.md |   65 +-

 wiki/pages/2026-08-20-fix-allowlist-tests.md       |   50 +-

 .../2026-08-20-review-gh-auth-mount-changes.md     |   60 +-

 .../pages/2026-08-21-mnt-176-bump-version-error.md |   90 +-

 ...26-08-24-gh-config-dir-permission-entrypoint.md |  123 +-

 wiki/pages/2026-08-24-guard-empty-plan-output.md   |   74 +-

 wiki/pages/2026-08-25-loader-styleguide.md         |  143 +-

 .../2026-08-25-mnt-181-total-tokens-counter.md     |  111 +-

 .../2026-08-25-mnt-187-wiki-pages-not-generated.md |   91 +-

 ...-awaiting-input-workflow-continues-to-review.md |   80 +-

 .../pages/2026-08-28-fix-index-lock-concurrency.md |   41 +-

 ...8-28-mnt-177-workflow-blocked-openrouter-403.md |   56 +-

 wiki/pages/2026-08-28-mnt-188-waitlist.md          |  108 +-

 ...2026-08-28-mnt-191-ticket-status-not-changed.md |  114 +-

 wiki/pages/2026-08-31-mnt-192-env-edit-button.md   |   96 +-

 wiki/pages/2026-09-01-mnt-177-research-loop.md     |  138 +-

 .../2026-09-02-mobile-template-react-frontend.md   |  133 +-

 wiki/pages/2026-09-02-review-findings-cleanup.md   |  137 +-

 wiki/pages/2026-09-08-docstring-mcp-search.md      |   72 -

 .../2026-09-08-opencode-reasoning-token-zero.md    |   36 +-

 .../2026-09-10-mnt-200-update-research-loop.md     |   78 --

 ...1-mnt-203-create-related-ticket-for-research.md |   65 -

 .../2026-09-14-listener-readline-limit-crash.md    |   92 --

 .../2026-09-14-opencode-agent-prompts-hardening.md |  134 --

 wiki/pages/2026-09-14-research-plan-artifact.md    |   65 -

 ...2026-09-16-mnt-205-revise-merged-environment.md |  618 ---------

 ...2026-09-18-dockerfile-opencode-agents-skills.md |   97 --

 .../2026-09-24-mnt-219-session-log-autoscroll.md   |  688 ----------

 wiki/pages/2026-09-27-mnt-225-add-copy-button.md   |   74 -

 .../pages/2026-09-28-compose-langsmith-host-env.md |  227 ----

 ...26-09-30-mnt-228-intermediate-history-states.md |  101 --

 .../2026-10-05-mnt-232-update-research-flow.md     |  192 +++

 232 files changed, 10678 insertions(+), 9007 deletions(-)
```

## Build plan

## Implementation Plan
The implementation plan involves the following steps:

### 1. Add Issue Relation GraphQL Mutation
* Create `demetra/queries/create_issue_relation.gql` with the `IssueRelationCreate` mutation.
* The mutation will have the field shape of `update_issue_status.gql`/`create_issue.gql`.

### 2. Add `create_issue_relation` Helper
* In `demetra/services/linear/mutations.py`, add the `create_issue_relation` function.
* The function will load the new query via `service.get_query(name="create_issue_relation")` and run `service.graphql_request` with the input.
* The function will return `result["data"]["issueRelationCreate"]["success"]`.
* Re-export the `create_issue_relation` function in `demetra/services/linear/__init__.py`.

### 3. Update `create_linear_ticket` to Skip Empty …

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_ef2314203ffe3rEkhgo1cOltPV`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-232/update-research-flow
