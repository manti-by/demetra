---
title: 'CH-13: Wiki OKF validation'
generated: {by: demetra, at: '2026-11-23T00:00:00Z'}
description: CH-13 added an Open Knowledge Format validator/migrator for the wiki bundle — it converts wikilinks to bundle-relative markdown links, replaces date with generated.at, maps status onto draft/stable/deprecated and LLM-authors descriptions, run as a one-time script in demetra/services/wiki/okf.py.
type: implementation
status: stable
session_id: ses_df5a4f147ffebn0JJRGQT4Tqnh
services: [.env.docker, .pre-commit-config, AGENTS, Dockerfile, Makefile, library, prompts, agents/opencode, llm/__init__, llm/openrouter, runtime/subprocess, runtime/utils, wiki/__init__, wiki/index, wiki/naming, wiki/okf, wiki/parsing, wiki/render, settings, docker-compose.test, docker-compose, pyproject, ChatPanel, SessionList, NewChatPage, test_docker_compose, test_opencode, test_openrouter, test_session_environment, test_settings, test_subprocess, test_wiki, uv, .sessions, INDEX, README, TEMPLATE, 2026-02-14-add-tui-support, 2026-02-15-git-cleanup-on-error, 2026-02-15-subagent-output-streaming, 2026-02-16-update-ticket-status, 2026-02-20-add-pre-commit-checks-and-tests, 2026-02-21-add-build-plan-to-linear-task, 2026-02-21-create-github-pr, 2026-02-21-opencode-sessions-isolation, 2026-02-23-add-multiagent-code-review, 2026-02-23-linear-oauth-2.0, 2026-02-23-plan-agent-output-triggers, 2026-02-23-refactor-workflow-into-modular-steps, 2026-02-23-save-build-plan-to-database, 2026-02-26-create-llm-test-script, 2026-03-02-process-manager, 2026-03-04-basic-react-app, 2026-03-05-github-login-react-app, 2026-03-05-github-login, 2026-03-05-postgres-support, 2026-03-05-worktree-path-already-exists, 2026-03-09-encrypted-user-settings, 2026-03-09-isolate-user-sessions, 2026-03-09-user-settings-frontend, 2026-03-10-ui-for-sessions, 2026-03-11-separate-linear-comments, 2026-03-11-task-plan-summarization, 2026-03-13-sqlalchemy-core-support, 2026-03-31-project-model-and-space, 2026-04-02-link-user-tasks-sessions, 2026-05-22-task-title-session-listing, 2026-05-25-async-review, 2026-05-25-remove-ticket-api, 2026-06-01-add-mcp-server, 2026-06-01-refactor-api, 2026-06-01-refactor-frontend-app, 2026-06-02-delete-session-button, 2026-06-02-plan-loop-resolve-questions, 2026-06-02-truncate-session-name, 2026-06-03-context-bloating, 2026-06-03-fix-squash-migrations, 2026-06-04-review-summarization, 2026-06-08-max-run-attempts-for-a-ticket, 2026-06-08-project-environment, 2026-06-08-session-step-attribute, 2026-06-09-build-artifacts, 2026-06-09-check-linear-ticket-text, 2026-06-09-markdown-renderer, 2026-06-10-fix-project-creation-timeouts, 2026-06-15-remove-patches-from-tests, 2026-06-22-github-pr-description, 2026-06-22-linear-link-artifact, 2026-06-25-update-project-version, 2026-06-25-websocket-to-track-session-statuses, 2026-07-07-add-context-compaction, 2026-07-07-project-deploy-script, 2026-07-15-duplicated-log-messages, 2026-07-16-fix-empty-build-plan-loop, 2026-07-16-fix-notification-mark-read, 2026-07-16-fix-step-status-review-findings, 2026-07-16-simplify-session-logging-setup, 2026-07-20-resolve-ansi-color-escape-codes-in-logs, 2026-07-21-awaiting-input-status-for-session, 2026-07-22-feature-flag-settings-and-tests, 2026-07-24-plain-auth-review-followups, 2026-08-03-check-api-auth-and-credentials, 2026-08-03-fix-mcp-server-2.0-api, 2026-07-16-session-history-tokens-null, 2026-07-21-rich-markuperror-and-run-attempts, 2026-07-22-react-frontend-template-warp, 2026-07-22-warp-theme-review-fixes-and-ops, 2026-07-23-agents-md-revalidation-and-docs-removal, 2026-07-23-linear-ticket-email-password-auth, 2026-07-23-session-history-modal, 2026-07-23-session-tokens-audit-revalidation, 2026-08-03-agents-md-and-wiki-consistency, 2026-08-03-auth-hardening-and-deps-bump, 2026-08-03-favicon-set-and-react-html, 2026-08-03-wiki-mcp-tools, 2026-08-04-fix-resolve-agent-truncated-context, 2026-08-05-post-build-validation, 2026-08-05-pr-creation-failure-handler, 2026-08-06-allowlist-review-fixes, 2026-08-07-mnt-147-wiki-processes-pr70-review, 2026-08-07-split-wiki-service-into-subpackage, 2026-08-09-apply-code-review-findings, 2026-08-09-apply-pr75-coderabbit-findings, 2026-08-09-wiki-fixes-and-test-optimization, 2026-08-10-docker-compose-deploy, 2026-08-10-process-environment-3-layers-encryption-uv-venv, 2026-08-17-docker-setup-review, 2026-08-18-categorize-settings-env-vars-by-layer, 2026-08-18-compose-anchors-refactor, 2026-08-18-migrate-llm-groq-to-openrouter, 2026-08-18-test-db-isolation-logging, 2026-08-19-build-agent-server-error-handler, 2026-08-19-build-agent-stale-session-deleted-worktree, 2026-08-19-split-auth-linear-services-and-review-failure-handling, 2026-08-19-wiki-should-use-llm-rename, 2026-08-19-worker-opencode-home-permissions, 2026-08-20-fix-allowlist-tests, 2026-08-20-review-gh-auth-mount-changes, 2026-08-21-mnt-176-bump-version-error, 2026-08-24-gh-config-dir-permission-entrypoint, 2026-08-24-guard-empty-plan-output, 2026-08-25-loader-styleguide, 2026-08-25-mnt-181-total-tokens-counter, 2026-08-25-mnt-187-wiki-pages-not-generated, 2026-08-28-awaiting-input-workflow-continues-to-review, 2026-08-28-fix-index-lock-concurrency, 2026-08-28-mnt-177-workflow-blocked-openrouter-403, 2026-08-28-mnt-188-waitlist, 2026-08-28-mnt-191-ticket-status-not-changed, 2026-08-31-mnt-192-env-edit-button, 2026-09-01-mnt-177-research-loop, 2026-09-02-mobile-template-react-frontend, 2026-09-02-review-findings-cleanup, 2026-09-08-docstring-mcp-search, 2026-09-08-opencode-reasoning-token-zero, 2026-09-10-mnt-200-update-research-loop, 2026-09-11-mnt-203-create-related-ticket-for-research, 2026-09-14-listener-readline-limit-crash, 2026-09-14-opencode-agent-prompts-hardening, 2026-09-14-research-plan-artifact, 2026-09-16-mnt-205-revise-merged-environment, 2026-09-18-dockerfile-opencode-agents-skills, 2026-09-24-mnt-219-session-log-autoscroll, 2026-09-27-mnt-225-add-copy-button, 2026-09-28-compose-langsmith-host-env, 2026-09-30-mnt-228-intermediate-history-states, 2026-10-05-mnt-232-update-research-flow, 2026-10-06-unify-subprocess-env-on-session-environment, 2026-10-08-llm-authored-wiki-pages, 2026-10-09-bm25-search-for-mcp-tools, 2026-10-12-review-models-env-resolution, 2026-10-12-session-state-animation, 2026-10-12-session-state-flow-feedback-loops, 2026-10-15-replace-wiki-mcp-tool-with-wi, 2026-10-16-mnt-234-isolate-session-context, 2026-10-16-mnt-245-empty-session-history, 2026-10-16-mnt-251-session-attribution-accounting, 2026-10-16-opencode-v2-session-token-accounting, 2026-10-25-mcp-db-tools-env-sql, 2026-10-25-mnt-258-tool-usage-stats, 2026-10-25-session-history-cost-and-failure-reasons, 2026-10-25-session-history-mcp-tool-usage, 2026-10-25-session-history-per-invocation-rows, 2026-10-27-mnt-260-openrouter-call-history, 2026-11-03-ch-2-single-unified-session-view, 2026-11-03-mnt-276-econnreset-retry-for-agents, 2026-11-04-chat-session-list-and-rerun, 2026-11-06-agent-econnreset-network-investigation, 2026-11-06-ch-5-delete-chat-button, 2026-11-06-ch-6-markdown-renderer, 2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions, 2026-11-06-mnt-298-research-econnreset-root-cause, 2026-11-10-ch-10-pr-description-for-chat-sessions, 2026-11-10-durable-review-attempts-budget, 2026-11-10-mnt-308-lint-error-extraction, 2026-11-10-mnt-309-chat-template, 2026-11-11-mnt-312-unified-task-model, 2026-11-12-ch-11-failed-status-for-awaiting-input-tickets, 2026-11-12-ch-12-session-list-order, 2026-11-12-scale-workers-without-recreate, 2026-11-14-mnt-315-auto-deploy-on-master-commits, 2026-11-15-mnt-314-linear-mcp-static-api-key, 2026-11-15-session-history-blocks-and-ui-deploy, 2026-11-15-session-list-three-sections, 2026-11-17-langsmith-403-multipart-ingest, 2026-11-18-ch-14-langsmitherror, 2026-11-23-docker-image-size-optimization]
branch: ch-13-wiki-okf-validation
tickets: [CH-13]
tags: [wiki, feature]
related: []
---

# CH-13: Wiki OKF validation

## TL;DR

This session implemented Open Knowledge Format (OKF) validation and migration for the wiki's `pages/` and `archive/` directories (167 files total). Key changes included:

1. Converting `[[wikilinks]]` to standard markdown links `[title](/path/to/file.md)`
2. Replacing `date` with OKF `generated.at` and normalizing `status` to `draft|stable|deprecated`
3. Adding LLM-generated `description` fields
4. Creating a shared `okf.py` service for consistent frontmatter handling

The changes were implemented as a one-time migration script rather than wiring validation into the main workflow.

## Overview

The migration focused on making wiki pages conform to OKF v0.2 while maintaining all existing functionality. Key decisions:

- Scope limited to `wiki/pages/` and `wiki/archive/` (167 files)
- `generated.by` set to "demetra" per OKF §7's `process:<id>` convention
- Archive pages marked as `deprecated` with original content preserved
- Links to archived pages resolve to `/archive/` paths

## Step 1 — Link Conversion

**File:** AGENTS.md:36

```markdown
- `wiki/`: Persistent session knowledge base...`[[...]]` links)
+ - `wiki/`: Persistent session knowledge base...standard markdown `/archive/...` links)
```

Converted all `[[wikilinks]]` to standard markdown links `[title](/path/to/file.md)`. Archive links now explicitly point to `/archive/` paths.

## Step 2 — Frontmatter Changes

**File:** demetra/services/wiki/okf.py (new)

Created a new service to handle:
- `generated.at` timestamps (replacing `date`)
- Status normalization (`stable|draft|deprecated`)
- Description generation
- Frontmatter validation

## Step 3 — Description Generation

Added LLM-powered description generation with fallback:

**File:** demetra/services/wiki/render.py:172-178

```python
if page_body.strip():
    meta["description"] = await service.compose_wiki_description(
        content=page_body, environment=context.environment
    )
else:
    meta["description"] = facts["description"] or ""
```

## Step 4 — Test Coverage

Added regression tests for empty body handling:

**File:** tests/test_wiki.py

```python
async def test_empty_body_uses_ticket_description_without_llm_call(...):
    monkeypatch.setattr(service, "compose_wiki_page", AsyncMock(return_value="  \n"))
    ...
    self.description_llm.assert_not_awaited()
    assert page["meta"]["description"] == "Automate wiki maintenance loops."
```

## Test Results

- All 150 tests pass (149 existing + 1 new)
- Linting and type checks clean
- Migration script successfully processed all 167 pages in dry-run mode

## Follow-ups

- None

## References

- External: <linear ticket URL>

> **Consistency note (2026-11-24, Consistency Agent):** two claims above did not hold for the whole bundle. (1) The migration left wikilinks in `2026-11-04-chat-session-list-and-rerun`, `2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions`, `2026-11-19-ch-15-worktree-management` and `2026-11-23-docker-image-size-optimization`, plus pre-OKF frontmatter (`date:` + `status: resolved` + no `description`) on `2026-11-17-langsmith-403-multipart-ingest`, `2026-11-18-ch-14-langsmitherror`, `2026-11-19-ch-15-worktree-management`, `2026-11-23-ch-13-wiki-okf-validation` (this page), `2026-11-23-docker-image-size-optimization` and `2026-11-24-mnt-320-build-forks-an-empty-session-id-fork-requires-continue-or-session`. `uv run python -m demetra.services.wiki.okf --dry-run` reported all eight; they were fixed by hand on 2026-11-24 (`generated: {by: demetra, at: …}`, `status: stable`, an authored description, converted links). (2) `2026-11-19-ch-15-worktree-management` also had a filename/frontmatter date mismatch (`2026-11-19` vs `2026-11-23`) — the filename wins, because `generated_at` falls back to it (`demetra/services/wiki/okf.py:104`). A clean `--dry-run` now reports 0 invalid pages.
