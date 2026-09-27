---
title: 'MNT-225: Add copy button'
date: '2026-09-27'
type: implementation
status: resolved
session_id: ses_f1dd57f7dffeGEATu4YXakfdTP
services: [.coderabbit, .dockerignore, .gitattributes, .gitignore, build-agent, merge-agent,
  plan-agent, rebase-agent, research-agent, resolve-agent, review-agent, validate-agent,
  SKILL, AGENTS, Dockerfile, Makefile, README, bootstrap, api, listener, react, rq-dashboard,
  watcher, worker, library, queries, agents/opencode, daemons/watcher, linear/__init__,
  linear/config, linear/mutations, linear/tasks, llm/__init__, llm/config, llm/factory,
  llm/openrouter, persistence/database, runtime/project, runtime/utils, vcs/github,
  vcs/merge, vcs/rebase, wiki/render, settings, tools, workflows, docker-compose,
  main, a3b4c5d6e7f8_add_sessions_research_report_column, opencode, pyproject, App,
  LogConsole, SessionArtifacts.test, SessionArtifacts, SessionList.test, index, conftest,
  test_api, test_api_coverage, test_database, test_docstring_tools, test_github, test_linear,
  test_more_coverage, test_opencode, test_openrouter, test_project, test_rebase_service,
  test_session_environment, test_settings_layers, test_validate_workflow, test_wiki_tools,
  test_workflows, uv, app, appearance, core-plugins, graph, workspace, .sessions,
  INDEX, QUESTIONS, 2026-03-11-separate-linear-comments, 2026-03-11-task-plan-summarization,
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
  2026-09-27-mnt-225-add-copy-button]
branch: mnt-225-add-copy-button
tickets: [MNT-225]
tags: [wiki, feature, frontend]
related: [2026-06-09-build-artifacts.md, 2026-06-09-markdown-renderer.md]
---
# MNT-225: Add copy button

## TL;DR

A 'Copy' button has been added to the build plan modal footer, allowing users to copy the raw markdown text to the clipboard. The implementation includes feature detection for the clipboard API and feedback for the user. All tests have passed, and the necessary React components and wiki pages have been updated.

---

## Overview

The `SessionArtifacts.tsx` component has been extended to include the new 'Copy' button, which uses the `navigator.clipboard.writeText()` API to copy the markdown text. The `SessionArtifacts.test.tsx` file has been updated with new test cases, and a wiki page has been created to document the implementation details.

## Changed files

- `react/src/components/SessionArtifacts.tsx` — `Copy` button in the build plan modal footer, clipboard feature detection, 1.5s "Copied!" feedback, and invalidation of a pending copy when the modal closes.
- `react/src/components/SessionArtifacts.test.tsx` — tests for Copy button rendering, clipboard write, unavailable clipboard API, and a pending copy resolving after close.
- `wiki/INDEX.md` — index entry for this page under `Pages` and `React frontend / UI`.
- `wiki/pages/2026-09-27-mnt-225-add-copy-button.md` — this page.

## Stat

```text
react/src/components/SessionArtifacts.test.tsx   | 90 +++++++-
react/src/components/SessionArtifacts.tsx       | 41 ++++++-
wiki/INDEX.md                                   | 3 +-
wiki/pages/2026-09-27-mnt-225-add-copy-button.md | 125 ++++++++++
4 files changed, 259 insertions(+), 3 deletions(-)
```

## Build plan

## Implementation Plan
### Approach
The plan is to add a "Copy" button to the existing build-plan modal footer in `SessionArtifacts.tsx`. This button will copy the raw markdown text of the build plan to the clipboard when clicked and display "Copied!" as feedback for 1.5 seconds.

### Key Technical Decisions
- The `navigator.clipboard.writeText()` API will be used to write the markdown text to the clipboard.
- Feature detection will be implemented to handle cases where the clipboard API is unavailable.
- The `SessionArtifacts.tsx` component will be extended to include the new "Copy" button and related functionality.

### Implementation Steps
1. **Update `SessionArtifacts.tsx`**:
   - Add a `copied` state and a `copyResetRef` to track the feedback-reset timeout.
   - Implement the `handleCo…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_f1dd57f7dffeGEATu4YXakfdTP`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-225/add-copy-button
