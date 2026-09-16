# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages
- [Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications](pages/2026-09-14-listener-readline-limit-crash.md) — The GitHub notification listener crashes every poll with `ValueError: Separator is not found, and chunk exceed the limit`: `live_stream` reads subprocess stdout with `asyncio.StreamReader.readline()` (64KB limit) and `gh api /notifications --jq .` emits the whole notification array as one compact line that exceeds 64KB once the unread backlog grows. Zero notifications ever processed (2792 errors, 0 enqueues) — merge/rebase/fix-review comments never trigger. Diagnosis only; fix (`run_command_to_file` for `get_notifications`/`fetch_subject_body`) not yet applied. (2026-09-14)
- [MNT-204: Research result modal](pages/2026-09-14-research-plan-artifact.md) — Added "View Research Plan" link + modal mirroring the build-plan artifact — new `sessions.research_plan` column, Session persistence, API exposure, and `SessionArtifacts` UI with m…. (2026-09-14)
- [OpenCode agent system prompts — permission hardening, injection guards, and merge/rebase semantics](pages/2026-09-14-opencode-agent-prompts-hardening.md) — Hardened all 7 `.opencode/agents/*.md` prompts (only `research-agent.md` had `description`/`permission` before). (2026-09-14)
- [MNT-203: Create related ticket for research](pages/2026-09-11-mnt-203-create-related-ticket-for-research.md) — Research workflow now creates a related Linear ticket instead of posting a comment on the source ticket. (2026-09-11)
- [MNT-200: Update research loop](pages/2026-09-10-mnt-200-update-research-loop.md) — Research loop now persists the extracted report to new `sessions.research_report` column and uses a new `researched` StepType (navy-blue badge). (2026-09-10)
- [OpenCode Reasoning Token History Is Zero](pages/2026-09-08-opencode-reasoning-token-zero.md) — Demetra persists `reasoning` from `opencode export` unchanged — zeros originate in OpenCode, not in API/frontend/DB. (2026-09-08)
- [MNT-171: Docstring MCP search](pages/2026-09-08-docstring-mcp-search.md) — MCP server now exposes `docstring_search`/`docstring_get`/`docstring_list` — ranked qualified names + snippets, full docstring by name, and catalog dump. (2026-09-08)
- [Review findings cleanup — v1.16.7..HEAD two-axis review](pages/2026-09-02-review-findings-cleanup.md) — Standards/Spec review of changes since `v1.16.7` then applied findings: removed dead code, extracted four duplication clusters (BE 202-response, encrypted-secret resolution, review…. (2026-09-02)
- [MNT-193 — Mobile template for the React frontend](pages/2026-09-02-mobile-template-react-frontend.md) — Mobile-responsive template for `react/src` per MNT-193 (MNT-174 mockups adapted to `SessionSidebar`/`SessionList`/`LogConsole`/`Header`). (2026-09-02)
- [MNT-177 research loop — research agent, workflow and settings](pages/2026-09-01-mnt-177-research-loop.md) — Added Research loop: tickets with `Research` label run a read-only `research-agent` (wiki + web validation) that extracts `## Research Report`, posts it as a Linear comment, and mo…. (2026-09-01)
- [MNT-192 Add edit button for env settings](pages/2026-08-31-mnt-192-env-edit-button.md) — Added pencil edit button to every env var row in `EnvSettings` and `SharedEnvSettings` modals with inline edit, rename via delete+re-add, duplicate-key guard, sorted display, and b…. (2026-08-31)
- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — Watcher created a pending session and enqueued a workflow for TODO tickets but never moved the Linear ticket to `In Progress` itself — that update lived only in `main.py` after `se…. (2026-08-28)
- [MNT-188: Waitlist](pages/2026-08-28-mnt-188-waitlist.md) — Blocked users can join a waitlist (HTTP 202) and admins approve entries via CLI to promote them to the allowlist. (2026-08-28)
- [MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation](pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md) — MNT-177 retried 6× on 2026-08-28 and never left the plan step. (2026-08-28)
- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md) — Implementation of Fix wiki index lock not process-safe (2026-08-28) (2026-08-28)
- [Workflow proceeds to review after ticket moved to Awaiting Input](pages/2026-08-28-awaiting-input-workflow-continues-to-review.md) — Implementation of Workflow proceeds to review after ticket moved to Awaiting Input (2026-08-28) (2026-08-28)
- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) — Implementation of Wiki pages not generated — move wiki step before commit (2026-08-25) (2026-08-25)
- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — Implementation of MNT-181: Total tokens counter (2026-08-25) (2026-08-25)
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — Implementation of Loader replacement and Style Guide page (2026-08-25) (2026-08-25)
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md) — Implementation of Guard empty plan agent output (2026-08-24) (2026-08-24)
- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — Implementation of gh config.yml permission denied in containers — un-gated entrypoint ownership repair (2026-08-24) (2026-08-24)
- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — Implementation of MNT-176: Bump version error fix (2026-08-21) (2026-08-21)
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md) — Implementation of Code review — gh CLI auth mount and entrypoint prune for compose (2026-08-20) (2026-08-20)
- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — Implementation of Fix allowlist tests after MNT-173 default-on refactor (2026-08-20) (2026-08-20)
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md) — Implementation of Worker opencode EACCES on home volume — entrypoint ownership fix (2026-08-19) (2026-08-19)
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md) — Implementation of Rename wiki budget_exceeded to should_use_llm (2026-08-19) (2026-08-19)
- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — Implementation of Split auth/linear services into subpackages + review-failure handling (2026-08-19) (2026-08-19)
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md) — Implementation of Build agent UnknownError — stale opencode session bound to deleted worktree (2026-08-19) (2026-08-19)
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md) — Implementation of Build agent server error — root cause and Awaiting Input handler (2026-08-19) (2026-08-19)
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — Tests wrote into the production `demetra` DB and spammed `/var/log/demetra/demetra.log` because `setup_test_db` wasn't autouse and `runtime/tui.py` installs a `FileHandler` at impo…. (2026-08-18)
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — Replaced Groq with OpenRouter for all LLM summarization (plan extraction, review, ticket breakdown, wiki polish, PR descriptions) via a single `build_llm()` factory over `langchain…. (2026-08-18)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — DRY refactor of `docker-compose.yaml`: six `mantiby/demetra:latest` services repeated ~20 identical lines; introduced three YAML anchors (`x-demetra-env`, `x-demetra-base`, `x-deme…. (2026-08-18)
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — Classified every workflow env var in `demetra/settings.py` into three layers — **project** (`project_environment`), **user** (`user_environment` `scope='user'`), or **system** (sta…. (2026-08-18)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — Review of `mnt-164-docker-compose` found the previously-verified Docker setup regressed with multiple blockers preventing boot — missing source copy, stale venv path, `WORKDIR` typ…. (2026-08-17)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — Extended per-project env into three layers — OS (allowlisted) → user-shared → project → step (last writer wins). (2026-08-10)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — Added a parallel `docker-compose.yaml` path running the full stack (Postgres, Redis, api, 4 workers, watcher, listener, rq-dashboard, one-shot React build) on `mantiby/demetra`. (2026-08-10)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — Hardened four wiki-service edge cases from the subpackage split (blank env paths, cluster scoring, last-header insertion, unreadable files, `answer_sweep` preamble) and scoped reva…. (2026-08-09)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — Applied 5 CodeRabbit findings on PR #75: versioned JWTs via `password_version` to close the post-snapshot race, fixed `Request`-aware `authFetch` origin guard, rejected negative `e…. (2026-08-09)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — Applied all 7 findings from post-refactor review (`CODE_REVIEW_FINDINGS.md`, `v1.15.4..HEAD`): restored cross-origin auth cookies, rejected negative `env_get_int`, gated validate-a…. (2026-08-09)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — Split monolithic `demetra/services/wiki.py` (1254 lines) into `demetra/services/wiki/` with six submodules behind a facade `__init__.py` re-exporting all 55 symbols. (2026-08-07)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — PR #70 was MERGEABLE (UNSTABLE while CI failed). (2026-08-07)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — Applied all actionable CodeRabbit findings on PR #71 (MNT-155 allowlist): de-prefixed functions, moved flag to `demetra/settings`, hardened admin bypass to immutable GitHub ID, val…. (2026-08-06)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — `gh pr create` failures after a successful push previously reverted the ticket to TODO with no Linear trace. (2026-08-05)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — Added a read-only `validate-agent` between build and review that compares the staged diff against the build plan and reports only uncovered plan steps. (2026-08-05)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — Implementation of Plan loop resolve agent received truncated context (2026-08-04) (2026-08-04)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Implementation of Wiki MCP Tools — Search, Read, and List Pages (2026-08-03) (2026-08-03)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — Implementation of Fix MCP Server for the mcp 2.0 API (2026-08-03) (2026-08-03)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Implementation of Favicon Set for the React App (2026-08-03) (2026-08-03)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — Implementation of Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene (2026-08-03) (2026-08-03)
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — Implementation of Password Hashing, Cookie & CORS Hardening, and Dependency Bump (2026-08-03) (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated `AGENTS.md` against the current codebase (wiki section added, f-string exception for `demetra/services/llm/prompt.py`, underscore-helper naming ban confirmed, deps move…. (2026-08-03)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implementation of Plain Password Auth Implementation and Review Follow-ups (2026-07-24) (2026-07-24)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Implementation of Session History & Token Consumption Audit (Revalidated) (2026-07-23) (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Implementation of Session History Modal (2026-07-23) (2026-07-23)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Implementation of Linear Ticket for Email/Password Authentication (2026-07-23) (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — Implementation of AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command (2026-07-23) (2026-07-23)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Implementation of Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette (2026-07-22) (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Implementation of React Frontend Layout, Template Updates, and Warp Theme CSS Refinements (2026-07-22) (2026-07-22)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Implementation of Add tests for existing feature-flag changes (2026-07-22) (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — Implementation of Rich MarkupError kills workflow subprocess and run_attempts counter overcounts (2026-07-21) (2026-07-21)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — Sessions with plan-agent questions no longer flip to `Failed` — they now enter an `Awaiting Input` state (stored as `step="awaiting_input"`). (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Raw ANSI escape sequences (`\x1b[31m` etc.) in logs rendered as garbled text. (2026-07-20)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Behavior-preserving refactor of `setup_session_logging()` (`demetra/services/utils.py`) after the dedup fix in [[2026-07-15-duplicated-log-messages]]: dropped unused `logger` param…. (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Two causes for NULL `session_history` tokens: the local DB was missing migration `a2b3c4d5e6f7` (every INSERT failed silently), and on odin prod the migration was applied but all 3…. (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Code review of the `status`→`step` migration surfaced 4 findings — drifted duplicate step enum, `status`/`step` naming conflation in the API, stale hardcoded return in `upsert_pend…. (2026-07-16)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Two listener bugs fixed: (1) `process_merge/rebase_notification` returned `bool` success but `demetra/listener.py` discarded it and always called `mark_notification_read` — failed …. (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Fixed a permanent stall where a run failing before plan save left `step='failed'` + empty `build_plan` → next run skipped planning (`step == 'initial'` gate) and exited forever. (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Two build-workflow logging bugs fixed: (1) `print_message()` lines duplicated in session logs because `setup_session_logging()` compared `Path` to `str` (always `False`), adding a …. (2026-07-15)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — Added a fast deploy path: `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, with systemd units and nginx. (2026-07-07)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — Added automatic context-length tracking and compaction for OpenCode sessions. (2026-07-07)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — Rebuilt the session-log websocket from raw text to typed JSON (`{"type":"log"}` / `{"type":"status"}`) so the React app distinguishes log lines from status transitions. (2026-06-25)
- [Update project version](pages/2026-06-25-update-project-version.md) — Every feature/bugfix workflow now auto-bumps `pyproject.toml`; major bumps are manual. (2026-06-25)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — Session artifacts now include a "View Linear Issue" link. (2026-06-22)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — PRs now get a generated description instead of an empty body: a Groq-backed service summarises the completed work and the text is passed as the GitHub PR body. (2026-06-22)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — Replaced `patch` DB mocks with fixtures/factories and local service calls with real invocations (third-party calls may stay mocked). (2026-06-15)

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### Workflow orchestration & agents (20 pages)

- [OpenCode agent system prompts — permission hardening, injection guards, and merge/rebase semantics](pages/2026-09-14-opencode-agent-prompts-hardening.md) — 2026-09-14
- [MNT-200: Update research loop](pages/2026-09-10-mnt-200-update-research-loop.md) — 2026-09-10
- [OpenCode Reasoning Token History Is Zero](pages/2026-09-08-opencode-reasoning-token-zero.md) — 2026-09-08
- [Review findings cleanup — v1.16.7..HEAD two-axis review](pages/2026-09-02-review-findings-cleanup.md) — 2026-09-02
- [MNT-177 research loop — research agent, workflow and settings](pages/2026-09-01-mnt-177-research-loop.md) — 2026-09-01
- [MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation](pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md) — 2026-08-28
- [Workflow proceeds to review after ticket moved to Awaiting Input](pages/2026-08-28-awaiting-input-workflow-continues-to-review.md) — 2026-08-28
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md) — 2026-08-24
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md) — 2026-08-20
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md) — 2026-08-19
- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — 2026-08-19
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md) — 2026-08-19
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md) — 2026-08-19
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — 2026-08-18
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — 2026-08-05
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — 2026-08-04
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — 2026-07-23
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — 2026-07-22
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — 2026-07-16
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — 2026-07-15

### MCP / integrations (11 pages)

- [MNT-203: Create related ticket for research](pages/2026-09-11-mnt-203-create-related-ticket-for-research.md) — 2026-09-11
- [MNT-171: Docstring MCP search](pages/2026-09-08-docstring-mcp-search.md) — 2026-09-08
- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md) — 2026-08-28
- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) — 2026-08-25
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md) — 2026-08-19
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — 2026-08-09
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — 2026-08-07
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — 2026-08-07
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — 2026-08-03
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — 2026-08-03
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — 2026-08-03
- [MNT-205: Revise merged environment](pages/2026-09-16-mnt-205-revise-merged-environment.md) — 2026-09-16

### React frontend / UI (8 pages)

- [MNT-204: Research result modal](pages/2026-09-14-research-plan-artifact.md) — 2026-09-14
- [MNT-193 — Mobile template for the React frontend](pages/2026-09-02-mobile-template-react-frontend.md) — 2026-09-02
- [MNT-192 Add edit button for env settings](pages/2026-08-31-mnt-192-env-edit-button.md) — 2026-08-31
- [MNT-188: Waitlist](pages/2026-08-28-mnt-188-waitlist.md) — 2026-08-28
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — 2026-08-25
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — 2026-08-03
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — 2026-07-22
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — 2026-06-22

### Linear & GitHub integrations (8 pages)

- [Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications](pages/2026-09-14-listener-readline-limit-crash.md) — 2026-09-14
- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — 2026-08-28
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — 2026-08-18
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — 2026-08-10
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — 2026-08-05
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — 2026-07-16
- [Update project version](pages/2026-06-25-update-project-version.md) — 2026-06-25
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — 2026-06-22

### Sessions, status & resume (7 pages)

- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — 2026-08-25
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — 2026-07-23
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — 2026-07-23
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — 2026-07-21
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — 2026-07-16
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — 2026-07-16
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — 2026-06-25

### Authentication & API security (7 pages)

- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — 2026-08-09
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — 2026-08-09
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — 2026-08-06
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — 2026-08-03
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — 2026-08-03
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — 2026-07-24
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — 2026-07-23

### Deploy & infrastructure (5 pages)

- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — 2026-08-24
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — 2026-08-18
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — 2026-08-17
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — 2026-08-10
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — 2026-07-07

### Testing & tooling (4 pages)

- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — 2026-08-20
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — 2026-08-18
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — 2026-07-22
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — 2026-06-15

### Logging infrastructure (2 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — 2026-07-20
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — 2026-07-16

### Docs, feature flags & release tooling (1 page)

- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — 2026-08-21

### TUI & CLI (1 page)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — 2026-07-21

### Context, tokens & compaction (1 page)

- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — 2026-07-07
