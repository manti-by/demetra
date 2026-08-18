# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — MNT-169: every workflow-runtime env var in `demetra/settings.py` classified into project / user / system layers per the MNT-161 three-layer model; Linear states+team → user, OpenRouter base URL → system / API key+model → user, `UV_PATH` → project, other tool paths → system; follow-up migration plan as comment block (2026-08-18)
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — MNT-168: new `demetra/services/llm/openrouter.py` (single `build_llm()` factory, `ChatOpenAI` + `OPENROUTER_*` config) serves all plan/review/cleanup/wiki consumers; legacy `groq.py` untouched; `WIKI_GROQ_BUDGET_*` → `WIKI_LLM_BUDGET_*`; 817 tests + all gates green (2026-08-18)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — DRY refactor of the merged compose: `x-demetra-env` / `x-demetra-base` / `x-demetra-app` YAML anchors shared across migrate/api/worker/watcher/listener/rq-dashboard via `<<:`; each service declares only `command`, `LOG_PATH`, `ports`, `replicas`; render-diff-verified equivalent (2026-08-18)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — code review of the in-progress `mnt-164-docker-compose` branch: 20 findings — 7 blockers (no source COPY, venv path mismatch, WORKDIR typo, missing healthchecks, watcher/listener DB_HOST, image-tag mismatch, missing psycopg-binary), 1 security-critical (`.keys/` baked into image via missing `.dockerignore` entry), 1 security regression (api + rq-dashboard published on `0.0.0.0` instead of loopback) (2026-08-17)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — MNT-164: parallel `docker-compose.yaml` path (Postgres + Redis + api/worker x4/watcher/listener/rq-dashboard + one-shot React build) on `mantiby/demetra`; `make docker-deploy` + `docker-*` targets; runtime fixes: pg18 mount, LOG_PATH, one-shot sequencing, rq-dashboard loopback, app-data volume, psycopg-binary (2026-08-10)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — MNT-161: OS (allowlisted) → user-shared → project → step merged in one `build_subprocess_env`; Fernet encryption via `DEMETRA_SECRET_KEY`; sensitive-key masking (`TOKEN|SECRET|KEY|PASSWORD`); `/users/me/env` CRUD; per-project `uv venv` bootstrap; FE Shared Environment screen + client-side `.env` upload (2026-08-10)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — Applied all 5 CodeRabbit findings on PR #75: `password_version` column closes the reset-token snapshot race, `authFetch`/`authenticatedFetch` handle `Request` inputs, `env_get_int` rejects negative defaults, `get_transaction` named arg, Step 6 wiki doc synced; migration a4b5c6d7e8f9, 739 passed in 4.95s (2026-08-09)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — Applied all 7 review findings (v1.15.4..HEAD): cross-origin auth cookies restored, `env_get_int` rejects negatives, validate-agent marker filter, `get_transaction()` atomicity for reset_password/delete_project, dedup keeps distinct tickets, porcelain `-z` parsing, typed auth exceptions; 1.16.3, 737 passed in 4.84s (2026-08-09)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — Hardened wiki edge cases (blank env paths, cluster scoring/insertion, unreadable pages, answer_sweep preamble + async I/O), scoped revalidation commits to changed files only; optimized slowest tests (seed rows patch, get_linear_task_by_id mock) — full suite 729 passed in 4.60s (2026-08-09)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — Implementation: split `demetra/services/wiki.py` (1254 lines) into a `wiki/` package — six submodules (parsing, naming, facts, index, render, maintenance) behind a facade `__init__.py` re-exporting all 55 symbols; submodules read state via `service.<NAME>` at call time so patch/monkeypatch seams hold; 728 tests + full gates pass (2026-08-07)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — PR #70 open but CONFLICTING/DIRTY; CI fails on `test_run_review_agents_filters_thinking_prose` because `env_get_list` (demetra/services/utils.py) returns `[]` instead of defaults when env var unset, emptying `OPENCODE_REVIEW_MODELS`; branch one merge behind master (MNT-155); 3 CodeRabbit threads open (2026-08-07)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — Applied CodeRabbit findings on PR #71 (MNT-155): renamed `_`-prefixed functions, flag from `demetra.settings`, admin bypass bound to immutable `github_id`, seed-file validation + dry-run, fixed `ck_users_has_auth` CI failures (2026-08-06)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — Implementation: new read-only validate-agent + prompt checking staged diff against the build plan before review; missing items loop inside MAX_REVIEW_ATTEMPTS; OPENCODE_VALIDATE_MODEL; fix replaced 4095-char prompt truncation with stdin piping and added BuildError on non-zero validate exit; version 1.16.0; PR #72 open (2026-08-05)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — Debug: in `--auto --plan-loop`, `shlex.quote(task)[:4095]` clipped the resolve-agent prompt so the numbered questions were dropped and the agent refused to act; first fix (`--file` temp file) broke every agent with "must provide a message", reverted to positional arg with the cap removed (2026-08-04)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — When `gh pr create` fails after the branch was pushed, a dedicated `except PullRequestError` in `main.py` posts a Linear comment (branch + compare URL + error), moves the ticket to `Awaiting Input` and records the session step as `awaiting_input` instead of silently reverting to TODO (2026-08-05)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Implementation: new demetra/tools/wiki.py exposing wiki_search/wiki_get_page/wiki_list_pages (frontmatter parsing, weighted ranking, line snippets, traversal-safe resolution), aggregate wiring, pyyaml dep, 1.15.6 bump, 28 tests; merged as PR #68 (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated AGENTS.md (wiki section, prompt.py f-string exception, underscore-prefix naming ban, deps pointer, GitHub+Groq), regenerated INDEX topic clusters, resolved stale PR #66/#67 + `47d428d` merge claims against master; PR #68 merged (2026-08-03)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — Debug: mcp 2.0.0 removed @server.list_tools()/@server.call_tool() decorators; rewrote demetra/mcp_server.py with on_list_tools/on_call_tool constructor callbacks returning ListToolsResult/CallToolResult, verified over stdio (2026-08-03)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Generated favicon set (.ico + PNGs + webmanifest) from media/logo.svg via sharp (cairosvg blocked by missing cairo), hand-built multi-size favicon.ico, wired icon links into react/index.html (2026-08-03)
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — Replaced passlib with direct bcrypt, made cookie SameSite and CORS origins env-configurable, released 1.15.5 with a dependency bump, added OpenCode release-naming command (2026-08-03)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — Shared `get_current_user_dep`, per-user session ownership in watcher, accept-then-close WebSocket rejection codes, credentials only on authenticated React calls plus Origin guard for mutations (2026-08-03)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implemented password-based signup/login/logout with bcrypt hashing, JWT cookies, React auth form; review follow-ups: cookie-only auth, email normalization, `--resetpass` CLI, migration for existing GitHub users (2026-07-24)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigation: mapped current GitHub-only auth (BE/FE/DB/tests), locked bcrypt + signup/login + single-table decisions via Q&A, produced [MNT-148](https://linear.app/mnt/issue/MNT-148) with file:line refs, AC, and out-of-scope follow-ups (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — AGENTS.md drift fixes, DOCS.md deleted (391 lines), new OpenCode command for automated AGENTS.md maintenance, LangSmith plugin registration, wiki housekeeping (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Implemented: new `GET /sessions/{task_id}/history` endpoint, `get_session_id_by_task_id` resolver, SessionHistory React component, tests across all layers (2026-07-23)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Merged audit + revalidation: 192-row stats from Odin DB, all confirmed; two causal claims refuted (pipe truncation vs cleanup ordering, cumulative counter vs context threshold); `length` is cumulative so compaction threshold was broken by design; 8 corrected recommendations (build plan since implemented in `47d428d`) (2026-07-23)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Post-merge MNT-142 review cleanups, bump_project_version hardened (warn+None), Makefile signing-key+pinned fast-playwright-mcp, green-accent palette switch, typography-to-index.css, table styles (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Merged: component structure map, gap removal, border-radius reorganization, SessionArtifacts always render, typography baseline, sidebar-footer, Playwright MCP (2026-07-22)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added FEATURES dict with IS_RUFF_ENABLED/IS_PYTEST_ENABLED env flags, gated lint workflow, added 6 new tests (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Debug: Rich `MarkupError` from a review finding with `[/.../]` regex crashed the workflow subprocess; escape markup in `print_message` and only increment `run_attempts` on actual failure (2026-07-21)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — MNT-140: added an `Awaiting Input` session state set after the plan agent posts questions to Linear, with custom failure states preserved through cleanup/history (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Fixed ANSI coloring issues by adding stripping filters at four levels in logging pipeline (2026-07-20)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Guarded mark_notification_read with success bool and added listener_attempts counter with a MAX_LISTENER_ATTEMPTS cap (default now 5) to break infinite retry loops (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Implementation: unified StepType/VALID_STEPS enum, renamed API `status`→`step`, fixed stale `upsert_pending_session` return value, documented divergent ON CONFLICT clauses (2026-07-16)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Implementation: behavior-preserving refactor — dropped unused `logger` param, single root-handler lookup, removed dead formatter fallbacks (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Implementation: replan on missing build_plan (not step), validate Linear response payload, enable fallback session ID recovery (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Debugged pipe truncation in opencode export causing NULL token columns; fixed with run_command_to_file temp-file approach (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Path==str dedup bug causing double writes, plus build agent stdout discarded instead of logged (2026-07-15)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — MNT-119: `Makefile deploy` target + `configs/bootstrap.sh` + systemd/nginx units for fast setup; GitHub/OpenCode auth via `.env` `EnvironmentFile` (2026-07-07)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — MNT-122: `session_history` table + OpenCode length/compact helpers + `CONTEXT_COMPACTION_THRESHOLD` (100k); disabled by MNT-145 (`5f8e428`), re-enabled live in `47d428d` (2026-07-07)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — MNT-101: rebuilt the session-log websocket to typed JSON (`log`/`status`) with frontend parsing and deduped status emission; supersedes MNT-53 raw-text log streaming (2026-06-25)
- [Update project version](pages/2026-06-25-update-project-version.md) — MNT-116: auto version bump in `pyproject.toml` (minor per feature/bug, major on `EPIC` label) with rollback on failure (2026-06-25)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — MNT-114: added `sessions.linear_link`, set on first save, exposed via API, shown as "View Linear Issue" in the artifacts panel (2026-06-22)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — MNT-115: Groq-generated PR description passed to GitHub PR creation, replacing the empty/placeholder body (2026-06-22)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — MNT-106: replaced patch mocks with fixtures/factories + real local calls, added amd64/ARM64 Docker support, trivial-review filtering (v1.13.0) (2026-06-15)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — MNT-97: removed the 120s timeout from OpenCode subprocess calls; renamed `SHELL_TIMEOUT_MS` -> `SUBPROCESS_TIMEOUT` (30-min default); merged MNT-112 configurable timeout protection (2026-06-10)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — MNT-113: added `marked` (^15.0.12) and a build-plan modal button that renders markdown to HTML (2026-06-09)
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md) — MNT-103: investigation validating `LinearTicket.text`; improved renderer (state filters, branch/labels, comment metadata, nested replies) (2026-06-09)
- [Build artifacts](pages/2026-06-09-build-artifacts.md) — MNT-108: persisted `pr_link` via migration, returned `pr_link`+`build_plan` from API, rendered artifacts block in React session log (2026-06-09)
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md) — MNT-83: `step` field on `Session` (initial/plan/build/lint/review/completed) for resuming interrupted workflows (2026-06-08)
- [Project environment](pages/2026-06-08-project-environment.md) — MNT-110: `Environment` model + cached `environment` dict on `Project` applied to every subprocess; MNT-109 was the closed partial attempt (2026-06-08)
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md) — MNT-100: `sessions.run_attempts` + `MAX_RUN_ATTEMPTS` guard (default 5 since `8ffc53b`) that moves the ticket to Awaiting Input on limit (2026-06-08)
- [Review summarization](pages/2026-06-04-review-summarization.md) — MNT-98: replaced `merge_review_results` with Groq+llama summary; deduped numbered findings, silent when none (2026-06-04)
- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md) — MNT-99: squashed migrations into one baseline; `alembic upgrade` runs clean; `repository_url` required (2026-06-03)
- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md) — MNT-105: debug — fixed `cwd` for plan/build/review/resolve subprocesses so agents scan the isolated worktree (v1.11.7) (2026-06-03)
- [Truncate session name](pages/2026-06-02-truncate-session-name.md) — MNT-92: CSS truncation of session titles fixes sidebar/console layout break, following `.session-plan` 120px (2026-06-02)
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md) — MNT-79: `--plan-loop` + `.opencode/agents/resolve-agent.md` loop between plan and resolve agents (max 30 attempts) (2026-06-02) — see also [[2026-08-04-fix-resolve-agent-truncated-context]]
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md) — MNT-86: delete button removes session + DB records + log files; list auto-refreshes (2026-06-02)
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md) — MNT-77: renamed `hera` frontend to `react`, tightened GitHub auth validation, removed legacy docs, bumped 1.10.0 (2026-06-01)
- [Refactor API](pages/2026-06-01-refactor-api.md) — MNT-81: split `demetra/api.py` into a package of per-prefix routers; added missing API tests (2026-06-01)
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md) — MNT-90: standalone `mcp_server.py` with streamable-http, filesystem CRUD, Postgres DB tools (2026-06-01)
- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md) — MNT-88: removed `demetra/api/tickets.py` + `demetra/services/ticket_provider.py` in favor of the Linear-native flow (2026-05-25)
- [Async review](pages/2026-05-25-async-review.md) — MNT-87: review agents run in parallel; `merge_review_results` handles `None` output; no empty commits (2026-05-25)
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md) — MNT-84: sessions API with status filter; session list shows task title with truncated-id fallback (2026-05-22)
_Newest first._

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### Workflow orchestration & agents (10 pages)

- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — validate-agent marker filter; all 7 review findings (v1.15.4..HEAD)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — PR #70 blocked: `env_get_list` regression empties `OPENCODE_REVIEW_MODELS`, branch behind master, 3 CodeRabbit threads open
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — MNT-146: validate-agent checks staged diff vs build plan before review; stdin delivery + BuildError on failure
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — 4095-char `[:4095]` cap clipped resolve-agent questions; dropped the cap (later superseded by stdin piping)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — MNT-140: session Awaiting Input state after questions
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — replan on missing build_plan, Linear payload validation
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md) — MNT-100: run-attempts guard (default 5)
- [Review summarization](pages/2026-06-04-review-summarization.md) — MNT-98: Groq+llama review findings summary
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md) — MNT-79: resolve-agent loop between plan and resolve agents
- [Async review](pages/2026-05-25-async-review.md) — MNT-87: parallel review agents

### Sessions, status & resume (7 pages)

- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — unified StepType/VALID_STEPS, API `status`→`step`
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — MNT-101: typed JSON websocket (`log`/`status`); supersedes MNT-53
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — MNT-114: Linear ticket link artifact
- [Build artifacts](pages/2026-06-09-build-artifacts.md) — MNT-108: PR link + build plan artifacts
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md) — MNT-83: `step` field for resuming interrupted workflows
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md) — MNT-86: delete session + related records
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md) — MNT-84: task title in session list

### React frontend / UI (7 pages)

- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Favicon set from logo.svg
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — history endpoint + SessionHistory component
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — MNT-142 review cleanups + green accent
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — MNT-142 component/layout map
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — MNT-113: `marked` in the build-plan modal
- [Truncate session name](pages/2026-06-02-truncate-session-name.md) — MNT-92: CSS truncation of session titles
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md) — MNT-77: `hera` → `react`

### Authentication & API security (6 pages)

- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — cross-origin auth cookies, typed auth exceptions, atomic reset_password/delete_project
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — MNT-155: allowlist review fixes (admin-by-github-id, seed validation)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — auth dependency consolidation, session ownership, WebSocket close codes
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — passlib→bcrypt swap, env-configurable cookie SameSite and CORS origins
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Password auth with bcrypt, JWT cookies, React form
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigation; produced MNT-148

### Linear & GitHub integrations (4 pages)

- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — `except PullRequestError` posts Linear comment + moves ticket to Awaiting Input, session step `awaiting_input`
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — listener mark-read gating + attempts cap
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — MNT-115: Groq PR description
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md) — MNT-103: renderer + comment metadata

### Database & migrations (2 pages)

- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — NULL token columns from pipe truncation
- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md) — MNT-99: squashed migration baseline

### API & services (4 pages)

- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — MNT-161: 3-layer env merge + encryption + venv + .env upload
- [Project environment](pages/2026-06-08-project-environment.md) — MNT-110: per-project env vars
- [Refactor API](pages/2026-06-01-refactor-api.md) — MNT-81: router package split
- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md) — MNT-88: removed tickets.py + ticket_provider.py

### Settings & environment layering (3 pages)

- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — MNT-169: every workflow-runtime env var in `demetra/settings.py` classified into project / user / system layers; follow-up migration plan as comment block
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — MNT-161: 3-layer env merge + encryption + venv + .env upload
- [Project environment](pages/2026-06-08-project-environment.md) — MNT-110: per-project env vars

### Context, tokens & compaction (3 pages)

- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — MNT-145: cumulative `length` breaks compaction threshold
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — MNT-122: `session_history` + compaction helpers
- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md) — MNT-105: cwd fix for underlying agents

### Logging infrastructure (3 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — ANSI stripping filters at four levels
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — behavior-preserving refactor
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Path==str dedup bug

### MCP / integrations (4 pages)

- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — wiki service split into 6 submodules + facade
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — wiki tools over MCP
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — mcp 2.0 migration
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md) — MNT-90: standalone `mcp_server.py`

### Testing & tooling (2 pages)

- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — FEATURES dict gating
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — MNT-106: fixtures/factories + Docker

### Docs, feature flags & release tooling (3 pages)

- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — AGENTS.md revalidation + INDEX regeneration
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — DOCS.md deleted, OpenCode command
- [Update project version](pages/2026-06-25-update-project-version.md) — MNT-116: auto version bump with rollback

### Deploy & infrastructure (4 pages)

- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — behavior-preserving YAML-anchor DRY refactor of the merged compose
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — code review of in-progress branch: 7 blockers + 1 security-critical (`.keys/` baked into image)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — MNT-164: docker-compose parallel deploy path (api/worker/watcher/listener/rq-dashboard + React build)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — MNT-119: Makefile deploy + bootstrap.sh + systemd

### TUI & CLI (1 page)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — MNT-136: markup escaping in `print_message`

### Subprocess & timeouts (1 page)

- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — MNT-97: `SUBPROCESS_TIMEOUT` (30 min) from OpenCode calls; merged MNT-112 timeout protection
