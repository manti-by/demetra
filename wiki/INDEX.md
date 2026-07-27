# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implemented password-based signup/login/logout with bcrypt hashing, JWT cookies, React auth form; review follow-ups: cookie-only auth, email normalization, `--resetpass` CLI, migration for existing GitHub users (2026-07-24)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigation: mapped current GitHub-only auth (BE/FE/DB/tests), locked bcrypt + signup/login + single-table decisions via Q&A, produced [MNT-148](https://linear.app/mnt/issue/MNT-148) with file:line refs, AC, and out-of-scope follow-ups (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — AGENTS.md drift fixes, DOCS.md deleted (391 lines), new OpenCode command for automated AGENTS.md maintenance, LangSmith plugin registration, wiki housekeeping (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Implemented: new `GET /sessions/{task_id}/history` endpoint, `get_session_id_by_task_id` resolver, SessionHistory React component, tests across all layers (2026-07-23)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Merged audit + revalidation: 192-row stats from Odin DB, all confirmed; two causal claims refuted (pipe truncation vs cleanup ordering, cumulative counter vs context threshold); `length` is cumulative so compaction threshold was broken by design; 8 corrected recommendations (2026-07-23)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Post-merge MNT-142 review cleanups, bump_project_version hardened (warn+None), Makefile signing-key+pinned fast-playwright-mcp, green-accent palette switch, typography-to-index.css, table styles (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Merged: component structure map, gap removal, border-radius reorganization, SessionArtifacts always render, typography baseline, sidebar-footer, Playwright MCP (2026-07-22)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added FEATURES dict with IS_RUFF_ENABLED/IS_PYTEST_ENABLED env flags, gated lint workflow, added 6 new tests (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Debug: Rich `MarkupError` from a review finding with `[/.../]` regex crashed the workflow subprocess; escape markup in `print_message` and only increment `run_attempts` on actual failure (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Fixed ANSI coloring issues by adding stripping filters at four levels in logging pipeline (2026-07-20)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Guarded mark_notification_read with success bool and added listener_attempts counter with MAX_LISTENER_ATTEMPTS=3 to break infinite retry loops (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Implementation: unified StepType/VALID_STEPS enum, renamed API `status`→`step`, fixed stale `upsert_pending_session` return value, documented divergent ON CONFLICT clauses (2026-07-16)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Implementation: behavior-preserving refactor — dropped unused `logger` param, single root-handler lookup, removed dead formatter fallbacks (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Implementation: replan on missing build_plan (not step), validate Linear response payload, enable fallback session ID recovery (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Debugged pipe truncation in opencode export causing NULL token columns; fixed with run_command_to_file temp-file approach (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Path==str dedup bug causing double writes, plus build agent stdout discarded instead of logged (2026-07-15)
_Newest first._

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### React frontend / UI (4 pages)

- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Password auth form, cookie-based API client, review follow-ups
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — New endpoint, resolver, SessionHistory component, tests
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — MNT-142 review cleanups, bump_project_version hardened, green-accent palette, infrastructure
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Component tree map, gap removal, border-radius reorganization, SessionArtifacts always render, typography baseline, sidebar-footer, Playwright MCP

### Workflow step / session state (3 pages)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Rich `MarkupError` from review finding crashed subprocess; escape markup, only increment `run_attempts` on failure
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Unified StepType, renamed API status→step, fixed upsert return value
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Replan on missing build_plan, validate Linear payload, enable fallback session ID

### Logging infrastructure (3 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — ANSI stripping filters at four levels in logging pipeline
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Behavior-preserving refactor of setup_session_logging
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Path==str dedup bug causing double writes, build agent stdout discarded

### Authentication (2 pages)

- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigation of current GitHub-only auth; produced MNT-148 for adding email/password alongside it
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Password auth with bcrypt, JWT cookies, React form, review follow-ups (also in React frontend)

### Session history & tokens (2 pages)

- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Merged audit + revalidation: 192-row stats, 8 corrected recommendations; `length` is cumulative so compaction threshold was broken by design
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Pipe truncation in opencode export causing NULL token columns

### Feature flags & documentation (2 pages)

- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — AGENTS.md drift fixes, DOCS.md deleted, new OpenCode command, LangSmith plugin, wiki housekeeping
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — FEATURES dict with IS_RUFF_ENABLED/IS_PYTEST_ENABLED env flags, gated lint workflow

### Notifications & listener (1 page)

- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Mark-as-read gating and listener_attempts counter
