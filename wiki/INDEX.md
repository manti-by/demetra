# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Implementation: new demetra/tools/wiki.py exposing wiki_search/wiki_get_page/wiki_list_pages (frontmatter parsing, weighted ranking, line snippets, traversal-safe resolution), aggregate wiring, pyyaml dep, 1.15.6 bump, 28 tests (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated AGENTS.md (wiki section, prompt.py f-string exception, `_`-helper naming, deps pointer, GitHub+Groq), regenerated INDEX topic clusters, resolved stale PR #66/#67 + `47d428d` merge claims against master (2026-08-03)
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
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Fixed ANSI coloring issues by adding stripping filters at four levels in logging pipeline (2026-07-20)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Guarded mark_notification_read with success bool and added listener_attempts counter with a MAX_LISTENER_ATTEMPTS cap (default now 5) to break infinite retry loops (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Implementation: unified StepType/VALID_STEPS enum, renamed API `status`→`step`, fixed stale `upsert_pending_session` return value, documented divergent ON CONFLICT clauses (2026-07-16)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Implementation: behavior-preserving refactor — dropped unused `logger` param, single root-handler lookup, removed dead formatter fallbacks (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Implementation: replan on missing build_plan (not step), validate Linear response payload, enable fallback session ID recovery (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Debugged pipe truncation in opencode export causing NULL token columns; fixed with run_command_to_file temp-file approach (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Path==str dedup bug causing double writes, plus build agent stdout discarded instead of logged (2026-07-15)
_Newest first._

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### Authentication & API security (4 pages)

- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — Auth dependency consolidation, session ownership, WebSocket close codes, React credential/Origin hygiene
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — passlib→bcrypt swap, env-configurable cookie SameSite and CORS origins, dep bump
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Password auth with bcrypt, JWT cookies, React form, review follow-ups (also in React frontend)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigation of GitHub-only auth; produced MNT-148 for adding email/password alongside it

### React frontend / UI (4 pages)

- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Favicon set from logo.svg, sharp rendering, hand-built favicon.ico, manifest + HTML wiring
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — New endpoint, resolver, SessionHistory component, tests (also in Session history & tokens)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — MNT-142 review cleanups, bump_project_version hardened, green-accent palette, infrastructure
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Component tree map, gap removal, border-radius reorganization, SessionArtifacts always render, typography baseline, sidebar-footer, Playwright MCP

### Workflow state & retries (4 pages)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Rich `MarkupError` from review finding crashed subprocess; escape markup, only increment `run_attempts` on failure
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Unified StepType, renamed API status→step, fixed upsert return value
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Replan on missing build_plan, validate Linear payload, enable fallback session ID
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Mark-as-read gating and listener_attempts counter

### Logging infrastructure (3 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — ANSI stripping filters at four levels in logging pipeline
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Behavior-preserving refactor of setup_session_logging
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Path==str dedup bug causing double writes, build agent stdout discarded

### Session history & tokens (2 pages)

- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Merged audit + revalidation: 192-row stats, 8 corrected recommendations; `length` is cumulative so compaction threshold was broken by design (build plan since implemented in `47d428d`)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Pipe truncation in opencode export causing NULL token columns

### Docs, feature flags & tooling (3 pages)

- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — AGENTS.md revalidation, wiki INDEX cluster regeneration, stale PR/commit claims resolved against master
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — AGENTS.md drift fixes, DOCS.md deleted, new OpenCode command, LangSmith plugin, wiki housekeeping
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — FEATURES dict with IS_RUFF_ENABLED/IS_PYTEST_ENABLED env flags, gated lint workflow

### MCP / integrations (2 pages)

- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — wiki_search/wiki_get_page/wiki_list_pages over wiki/pages, weighted ranking + snippets, wired into aggregate list_tools/call_tool
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — mcp 2.0 removed the list_tools/call_tool decorators; migrated to on_list_tools/on_call_tool constructor callbacks
