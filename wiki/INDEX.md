# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — On the MNT-170 env-layers branch, a follow-up refactor split the two remaining (2026-08-19)
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — The test suite was writing into the real `demetra` database and the production (2026-08-18)
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — Replaced the Groq-backed LLM service with OpenRouter for plan extraction, review (2026-08-18)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — Behavior-preserving refactor of `docker-compose.yaml`: the six `mantiby/demetra:latest` services (`migrate`, `api`, `worker`, `watcher`, `listener`, `rq-dashboard`) previously repeated ~20 identica... (2026-08-18)
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — Classifies every workflow-runtime env var read in `demetra/settings.py` into one of three target layers — **project** (per-project `project_environment` rows), **user** (per-user `user_environment`... (2026-08-18)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — The in-progress `mnt-164-docker-compose` branch has regressed the previously-verified Docker setup in [[2026-08-10-docker-compose-deploy]] and introduced **multiple critical blockers** that prevent... (2026-08-17)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — Extended per-project env ([MNT-110](https://linear.app/mnt/issue/MNT-110)) into a three-layer model — OS (allowlisted), user-shared (per-user), and project (per-project) — merged as **OS → user-sha... (2026-08-10)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — Added a parallel `docker-compose.yaml` deployment path that runs the full app layer (Postgres, Redis, api, worker x4, watcher, listener, rq-dashboard, one-shot React build) on top of the `mantiby/d... (2026-08-10)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — Hardened four wiki-service edge cases surfaced while exercising the freshly split subpackage (blank env paths, cluster scoring across multiple bullets, cluster insertion when the target header is t... (2026-08-09)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — Applied all 5 open CodeRabbit findings on PR #75 ("Code review of release candidate"): added a per-user `password_version` so JWTs minted concurrently with a password reset are rejected after it co... (2026-08-09)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — Applied all 7 findings from the post-refactor code review (`CODE_REVIEW_FINDINGS.md`, scope `v1.15.4..HEAD`): restored cross-origin auth cookies in the React client, rejected negative ints in `env_... (2026-08-09)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — Split the monolithic `demetra/services/wiki.py` (1254 lines) into a `demetra/services/wiki/` package: six submodules (`parsing`, `naming`, `facts`, `index`, `render`, `maintenance`) behind a facade... (2026-08-07)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — PR #70 (mnt-147-wiki-processes → master) is open; GitHub reports it MERGEABLE (UNSTABLE while CI fails) and both CI "Run checks" runs fail on `test_run_review_agents_filters_thinking_prose`. Root c... (2026-08-07)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — Applied every actionable CodeRabbit finding on PR #71 (MNT-155, registration/GitHub-login (2026-08-06)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — When `gh pr create` fails at the end of the workflow (after the branch was already pushed), the ticket used to be silently moved back to TODO with no trace on the Linear side. A dedicated `except P... (2026-08-05)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — Added a dedicated read-only `validate-agent` that runs after the build step and (2026-08-05)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — In `--auto --plan-loop` mode, the resolve agent was being handed only a truncated original task with no question list because `run_opencode_agent` passed the task as a `shlex.quote(task)[:4095]` po... (2026-08-04)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Implemented the wiki MCP tools module `demetra/tools/wiki.py` exposing three tools — (2026-08-03)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — `uv run python -m demetra.mcp_server` crashed at import time with (2026-08-03)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Generated a full favicon set (`.ico` + PNGs + PWA webmanifest) from the existing `media/logo.svg` and wired it into `react/index.html`. The source SVG is a dark `#25292e` square with a white glyph,... (2026-08-03)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — The `mnt-156-check-api-auth` branch (1 commit ahead of master, plus current (2026-08-03)
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — Working-tree change set on `master` (not yet committed): replaced the `passlib` (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated `AGENTS.md` against the current codebase (wiki section added, f-string (2026-08-03)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implemented password-based signup/login/logout alongside existing GitHub OAuth, (2026-07-24)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Demetra records one row per workflow step (`plan`, `build`, `completed`, `failed`, (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Add a "View History" button next to "View Build Plan" in `SessionArtifacts` that opens a modal showing the per-step session history rows (step name, timestamp, token-usage breakdown) as a vertical ... (2026-07-23)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigated the current GitHub-only auth flow (BE, FE, DB, tests) and produced a comprehensive Linear ticket **[MNT-148](https://linear.app/mnt/issue/MNT-148/featauth-add-emailpassword-authenticat... (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — Updated `AGENTS.md` to reflect the current codebase (project description, MCP tool module pattern, feature flags, missing `langsmith` dep), deleted the now-redundant `DOCS.md` (391 lines, all conte... (2026-07-23)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Post-merge review cleanup for MNT-142 (Warp theme), plus Makefile signing-key config, pinned `@tontoko/fast-playwright-mcp@0.1.3`, `bump_project_version` hardened to log+return `None` instead of ra... (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Merged from three sessions covering the React frontend end-to-end: mapped the component tree and flexbox layout, removed the gap between sidebar and console, reorganized border/background ownership... (2026-07-22)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added a `FEATURES` dict to `demetra/settings.py` that gates `ruff` and `pytest` execution via two env-var-driven flags (`IS_RUFF_ENABLED`, `IS_PYTEST_ENABLED`), both defaulting to `False`. The lint... (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — MNT-136 ("PWA & static asset migration") surfaced as `Max run attempts reached` after three (2026-07-21)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — Sessions no longer flip to `Failed` when the plan agent has questions and moves the Linear ticket to `Awaiting Input`. A `Session` can now be in an `Awaiting Input` state, set right after questions... (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — ANSI escape codes in logs were causing coloring issues. Fixed by adding a stripping filter at multiple levels. (2026-07-20)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Refactored `setup_session_logging()` in `demetra/services/utils.py` — it had grown hard to read (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Two separate causes were found. On the **local dev DB**, migration `a2b3c4d5e6f7` (adds token columns) was never applied — every INSERT failed silently. On the **odin production server**, the migra... (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Ran `/code-review` against the working-tree diff that migrated session tracking from a `status` (2026-07-16)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Two bugs in `listener.py`: (1) `process_merge_notification`/`process_rebase_notification` returned a `bool` indicating success, but `listener.py` discarded it and called `mark_notification_read` un... (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Fixed a permanent workflow stall where a run failing before a plan is saved (e.g., due to a Linear API `null` response) locks the session into an unplannable state. Three fixes: (1) replan whenever... (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Two logging bugs in the build workflow subprocess: (1) `print_message()` outputs appeared duplicated in session log files because `setup_session_logging()` had a dedup guard comparing `Path` to `st... (2026-07-15)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — Built a fast setup/deploy path: a `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, backed by systemd unit files and an nginx site. GitHub integration and Ope... (2026-07-07)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — Added automatic context-length checks and compaction for OpenCode agent sessions. A new `session_history` table records the context length after each workflow step, and when the recorded length exc... (2026-07-07)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — Rebuilt the session-log websocket from raw text frames to typed JSON so the React app can distinguish live log lines from status changes. The websocket now sends `{"type": "log", ...}` and `{"type"... (2026-06-25)
- [Update project version](pages/2026-06-25-update-project-version.md) — Added automatic version bumping in `pyproject.toml` on every feature/bugfix workflow. New features and bugs trigger a minor bump; tickets carrying the `EPIC` label trigger a major bump. The bump is... (2026-06-25)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — Added a link to the Linear ticket in the session artifacts. A `linear_link` field was added to `sessions` with a migration; it is set on the first session save when the Linear task is retrieved, se... (2026-06-22)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — PRs created from a completed feature now get a real description instead of an empty/placeholder body. A Groq-backed service summarises what was done and the generated text is passed when creating t... (2026-06-22)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — Refactored the test suite to drop as many `patch` mocks as possible: DB access now uses fixtures/factories and local service calls use real function calls, while third-party service calls may stay ... (2026-06-15)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — Project creation was timing out because `run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to OpenCode agent/subprocess calls too, killing long operations like clone and build. The fix remov... (2026-06-10)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — Added markdown-to-HTML rendering for the build plan in the React app using the `marked` library. A new button in the build-plan modal parses the raw markdown with `marked` and replaces it with the ... (2026-06-09)
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md) — Investigated what `LinearTicket.text` actually returns for resolved/unresolved comment threads, then used the findings to improve the Linear ticket renderer. Issues are now filterable by state, the... (2026-06-09)
- [Build artifacts](pages/2026-06-09-build-artifacts.md) — Session artifacts — the PR link and the build plan — are now persisted and shown in the React app. Added `pr_link` to the `session` model with an Alembic migration; the field is populated when a PR... (2026-06-09)
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md) — Added a `step` attribute to the `Session` model so an interrupted workflow can resume at the right step. Choices are `initial` (default), `plan`, `build`, `lint`, `review`, `completed`, and the fie... (2026-06-08)
- [Project environment](pages/2026-06-08-project-environment.md) — Added per-project environment variables that are applied to every subprocess the supervisor spawns. A new `Environment` model (`project_id` FK, `key`, `value`) holds one-to-many records per project... (2026-06-08)
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md) — Added a `run_attempts` counter to the `sessions` table and a `MAX_RUN_ATTEMPTS` project setting (default 3) so a Linear ticket cannot trigger an infinite chain of workflow runs. When the counter re... (2026-06-08)
- [Review summarization](pages/2026-06-04-review-summarization.md) — Review-agent findings are now summarized into one list by Groq + llama instead of being naively concatenated. A new prompt summarizes the review results; the simple `merge_review_results` was repla... (2026-06-04)
- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md) — Dropped the accumulated migration chain and replaced it with a single consolidated migration, updating the existing local database so `alembic upgrade` no longer errors. DB connection initializatio... (2026-06-03)
- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md) — `uv run main.py --project-name mgallery --auto --plan-loop` made the OpenCode plan agent scan `/Users/alexander/www/m2/demetra` directly instead of the isolated process worktree, bloating the agent... (2026-06-03)
- [Truncate session name](pages/2026-06-02-truncate-session-name.md) — Fixed a React layout bug where a long session name made the session list too tall and pushed the log console below it, breaking the intended left-right layout. The session item title box now fits w... (2026-06-02)
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md) — Automated the plan question round-trip: a separate resolve agent answers the plan agent's questions in `auto` mode instead of posting them to Linear. Added `.opencode/agents/resolve-agent.md` (chec... (2026-06-02)
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md) — Sessions can now be deleted entirely. A delete button sits near the clear button in the session log header; on click it sends a delete request to the API, which removes the session and all related ... (2026-06-02)
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md) — Refactored and renamed the `hera` frontend app to `react`, normalizing the directory after `hera` had existed as an early scaffold. The rename touched the frontend directory, the Makefile, and docs... (2026-06-01)
- [Refactor API](pages/2026-06-01-refactor-api.md) — Split the too-long `demetra/api.py` into a `demetra/api/` package with routers grouped by route prefix (auth/github, projects, sessions, users, watcher, webhooks). The package keeps `@app.get`/`@ap... (2026-06-01)
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md) — Added a basic MCP server as a single standalone `mcp_server.py` in the project root, using the `mcp` PyPI package. It exposes streamable-http transport on a configurable port (env), filesystem tool... (2026-06-01)
- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md) — Removed the ticket-creation-from-text API added earlier (`demetra/api/tickets.py` + `demetra/services/ticket_provider.py`, the `/create-ticket` AI-extraction endpoint). The routers and tests were u... (2026-05-25)
- [Async review](pages/2026-05-25-async-review.md) — Made the code-review step parallel: `run_review_agents` now runs all review agents asynchronously and merges their responses. The same PR (with MNT-86) fixed `merge_review_results` to handle `None`... (2026-05-25)
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md) — The session list now shows the task title instead of the truncated session id. The sessions API gained an endpoint with optional status filtering, sessions display a custom name when available with... (2026-05-22)

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### Workflow orchestration & session lifecycle (10 pages)

- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md)
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md)
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md)
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md)

### LLM pipeline & review agents (9 pages)

- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md)
- [Review summarization](pages/2026-06-04-review-summarization.md)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md)
- [Async review](pages/2026-05-25-async-review.md)

### Sessions, history & tokens (8 pages)

- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md)
- [Build artifacts](pages/2026-06-09-build-artifacts.md)
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md)
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md)

### React frontend / UI (6 pages)

- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md)
- [Session History Modal](pages/2026-07-23-session-history-modal.md)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md)
- [Truncate session name](pages/2026-06-02-truncate-session-name.md)

### Settings, environment & subprocess (5 pages)

- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md)
- [Project environment](pages/2026-06-08-project-environment.md)

### Wiki & MCP tools (5 pages)

- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md)
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md)

### Service architecture & refactoring (4 pages)

- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md)
- [Refactor API](pages/2026-06-01-refactor-api.md)
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md)

### Docker & deploy (4 pages)

- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md)

### Authentication & API security (3 pages)

- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md)

### Logging infrastructure (3 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md)

### Docs, versioning & wiki governance (3 pages)

- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md)
- [Update project version](pages/2026-06-25-update-project-version.md)

### Linear & GitHub integrations (2 pages)

- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md)
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md)

### Database & migrations (1 page)

- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md)

### Testing & CI (1 page)

- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md)

### Context & agent scanning (1 page)

- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md)

### Decommissioned (1 page)

- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md)
