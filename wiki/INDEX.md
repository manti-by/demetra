# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages
- [MNT-205 — Revise merged environment: context.environment resolver](pages/2026-09-16-mnt-205-revise-merged-environment.md) — The implementation standardized methods for resolving agent models, Linear settings, and OpenRouter settings by introducing a single SessionEnvironment resolver. (2026-09-16)
- [MNT-204: Research result modal](pages/2026-09-14-research-plan-artifact.md) — Added "View Research Plan" link + modal mirroring the build-plan artifact — new `sessions.research_plan` column, Session persistence, API exposure, and `SessionArtifacts` UI with markdown toggle. (2026-09-14)
- [OpenCode agent system prompts — permission hardening, injection guards, and merge/rebase semantics](pages/2026-09-14-opencode-agent-prompts-hardening.md) — Hardened all 7 `.opencode/agents/*.md` prompts (only `research-agent.md` had `description`/`permission` before). (2026-09-14)
- [Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications](pages/2026-09-14-listener-readline-limit-crash.md) — The GitHub notification listener (`demetra/listener.py`) has never processed a single notification: the log shows 2792 `Error polling GitHub notifications` tracebacks and **zero** `Processing notification` / `Enqueuing`... (2026-09-14)
- [MNT-203: Create related ticket for research](pages/2026-09-11-mnt-203-create-related-ticket-for-research.md) — Research workflow now creates a related Linear ticket instead of posting a comment on the source ticket. New ticket inherits project, priority, and state (`PRD`), with `Feature` plus source `Backend`/`Frontend` labels. (2026-09-11)
- [MNT-200: Update research loop](pages/2026-09-10-mnt-200-update-research-loop.md) — Research loop now persists the extracted report to new `sessions.research_report` column and uses a new `researched` StepType (navy-blue badge). Added migration, StepType/Session updates, and React/CSS changes. (2026-09-10)
- [OpenCode Reasoning Token History Is Zero](pages/2026-09-08-opencode-reasoning-token-zero.md) — Demetra persists `reasoning` from `opencode export` unchanged — zeros originate in OpenCode, not in API/frontend/DB. (2026-09-08)
- [MNT-171: Docstring MCP search](pages/2026-09-08-docstring-mcp-search.md) — MCP server now exposes `docstring_search`/`docstring_get`/`docstring_list` — ranked qualified names + snippets, full docstring by name, and catalog dump. (2026-09-08)
- [Review findings cleanup — v1.16.7..HEAD two-axis review](pages/2026-09-02-review-findings-cleanup.md) — Standards/Spec review of changes since `v1.16.7` then applied findings: removed dead code, extracted four duplication clusters (BE 202-response, encrypted-secret resolution, review-thread formatting, ~150-line React env... (2026-09-02)
- [MNT-193 — Mobile template for the React frontend](pages/2026-09-02-mobile-template-react-frontend.md) — Mobile-responsive template for `react/src` per MNT-193 (MNT-174 mockups adapted to `SessionSidebar`/`SessionList`/`LogConsole`/`Header`). (2026-09-02)
- [MNT-177 research loop — research agent, workflow and settings](pages/2026-09-01-mnt-177-research-loop.md) — Added Research loop: tickets with `Research` label run a read-only `research-agent` (wiki + web validation) that extracts `## Research Report`, posts it as a Linear comment, and moves the ticket to `Awaiting Input`. (2026-09-01)
- [MNT-192 Add edit button for env settings](pages/2026-08-31-mnt-192-env-edit-button.md) — Added pencil edit button to every env var row in `EnvSettings` and `SharedEnvSettings` modals with inline edit, rename via delete+re-add, duplicate-key guard, sorted display, and backend preservation of encrypted values... (2026-08-31)
- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — Watcher created a pending session and enqueued a workflow for TODO tickets but never moved the Linear ticket to `In Progress` itself — that update lived only in `main.py` after `setup_workflow` succeeded. (2026-08-28)
- [MNT-188: Waitlist](pages/2026-08-28-mnt-188-waitlist.md) — Blocked users can join a waitlist (HTTP 202) and admins approve entries via CLI to promote them to the allowlist. (2026-08-28)
- [MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation](pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md) — MNT-177 retried 6× on 2026-08-28 and never left the plan step. Dominant cause (3/6 runs) was OpenRouter 403 on `meta/muse-spark-1.2` requiring 18+ attestation; 2 runs truncated by auto-rejected `read (.env.docker.example... (2026-08-28)
- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md) — Wiki INDEX read-modify-write was only in-process serialized: `_INDEX_LOCK = asyncio.Lock()` plus `flock` taken only inside `_write_index_unlocked` after the read. (2026-08-28)
- [Workflow proceeds to review after ticket moved to Awaiting Input](pages/2026-08-28-awaiting-input-workflow-continues-to-review.md) — Same-run halt after posting questions works (`move_to_awaiting_input` raises `AutoCancelledError`), but the signal is not durable: the questions-run persists `build_plan` before posting questions and never re-checks Line... (2026-08-28)
- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) — Wiki pages were written in `main.py`'s `finally` after `commit_and_push` committed/pushed, targeting the main checkout (`WIKI_ROOT = BASE_PATH / "wiki"`) not the worktree — so `wiki/pages/*.md` never reached the repo. (2026-08-25)
- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — Added a session-wide **Total Tokens** summary to the history modal. `GET /api/v1/sessions/{task_id}/history` now returns `{"total": {...}, "history": [...]}` via `_compute_total_tokens` in `demetra/api/sessions.py` (sums... (2026-08-25)
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — Replaced all backend-waiting spinners with `react/public/loader.svg` (olive #788860) via a reusable `Loader` component, and added a living Style Guide at `/styleguide` linked from the burger menu cataloging all UI primit... (2026-08-25)
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md) — Workflow showed `No implementation plan was provided in the plan output` as the build plan — a hallucination by the `extract_plan` LLM given empty stdout. (2026-08-24)
- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — `gh auth` inside containers failed with `failed to write config after migration: open /home/demetra/.config/gh/config.yml: permission denied`. (2026-08-24)
- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — `bump_project_version` incorrectly bumped major for Epic-labeled tickets (`1.x.y → 2.0.0`); rule is major is manual-only. (2026-08-21)
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md) — Reviewed working-tree changes adding `gh` auth to Docker: bind mount `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` and matching `find -prune` entry. (2026-08-20)
- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — MNT-173 flipped the allowlist gate from default-off (`ALLOWLIST_ENABLED`/`is_allowlist_enabled()`) to default-on `IS_ALLOWLIST_ENABLED = env_get_bool(..., True)` (fail-closed), leaving 12 failures + 23 errors from tests... (2026-08-20)
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md) — Worker failed at plan step: `EACCES: permission denied, mkdir '/home/demetra/.local/share/opencode/repos'` — the `demetra_app_data` volume at `/home/demetra` (`docker-compose.yaml:15`) had root-owned dirs from before the... (2026-08-19)
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md) — Renamed wiki gate `budget_exceeded()` → `should_use_llm()` across `demetra/services/wiki/` and `tests/test_wiki.py`. (2026-08-19)
- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — On the MNT-170 branch (merged via PR #80, 2026-08-19), the `auth` and `linear` monolithic facades were split into per-concern submodules behind `__init__.py` facades and the `sys.meta_path` relocation shim was deleted fr... (2026-08-19)
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md) — After the spending limit was raised, MNT-151 kept failing with `UnknownError: Unexpected server error (err_...)` — not the limit but a stale `sessions.session_id` (`ses_fe96234f1ffeADBso4qFrnzE0Y`) bound to a worktree de... (2026-08-19)
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md) — MNT-151 builds failed ~4s after "Running BUILD agent" with `UnknownError: Unexpected server error (err_...)` exit 1. (2026-08-19)
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — Tests wrote into the production `demetra` DB and spammed `/var/log/demetra/demetra.log` because `setup_test_db` wasn't autouse and `runtime/tui.py` installs a `FileHandler` at import. (2026-08-18)
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — Replaced Groq with OpenRouter for all LLM summarization (plan extraction, review, ticket breakdown, wiki polish, PR descriptions) via a single `build_llm()` factory over `langchain-openai` `ChatOpenAI`. (2026-08-18)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — DRY refactor of `docker-compose.yaml`: six `mantiby/demetra:latest` services repeated ~20 identical lines; introduced three YAML anchors (`x-demetra-env`, `x-demetra-base`, `x-demetra-app`) merged via `<<:` so each servi... (2026-08-18)
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — Classified every workflow env var in `demetra/settings.py` into three layers — **project** (`project_environment`), **user** (`user_environment` `scope='user'`), or **system** (stays in `settings.py`, overridable by user... (2026-08-18)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — Review of `mnt-164-docker-compose` found the previously-verified Docker setup regressed with multiple blockers preventing boot — missing source copy, stale venv path, `WORKDIR` typo, `.keys/` baked into image, dropped he... (2026-08-17)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — Extended per-project env into three layers — OS (allowlisted) → user-shared → project → step (last writer wins). (2026-08-10)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — Added a parallel `docker-compose.yaml` path running the full stack (Postgres, Redis, api, 4 workers, watcher, listener, rq-dashboard, one-shot React build) on `mantiby/demetra`. Systemd `make deploy` unchanged. (2026-08-10)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — Hardened four wiki-service edge cases from the subpackage split (blank env paths, cluster scoring, last-header insertion, unreadable files, `answer_sweep` preamble) and scoped revalidation commits to changed files. (2026-08-09)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — Applied 5 CodeRabbit findings on PR #75: versioned JWTs via `password_version` to close the post-snapshot race, fixed `Request`-aware `authFetch` origin guard, rejected negative `env_get_int` defaults, named `db_name` ar... (2026-08-09)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — Applied all 7 findings from post-refactor review (`CODE_REVIEW_FINDINGS.md`, `v1.15.4..HEAD`): restored cross-origin auth cookies, rejected negative `env_get_int`, gated validate-agent on `Plan step N:` marker, made `res... (2026-08-09)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — Split monolithic `demetra/services/wiki.py` (1254 lines) into `demetra/services/wiki/` with six submodules behind a facade `__init__.py` re-exporting all 55 symbols. (2026-08-07)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — PR #70 was MERGEABLE (UNSTABLE while CI failed). Root cause: `env_get_list` in `demetra/services/utils.py:249` returned `[]` instead of the default when the env var was unset, so CI (without `OPENCODE_REVIEW_MODELS`) pro... (2026-08-07)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — Applied all actionable CodeRabbit findings on PR #71 (MNT-155 allowlist): de-prefixed functions, moved flag to `demetra/settings`, hardened admin bypass to immutable GitHub ID, validated seed-file entries, made seed CLI... (2026-08-06)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — `gh pr create` failures after a successful push previously reverted the ticket to TODO with no Linear trace. (2026-08-05)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — Added a read-only `validate-agent` between build and review that compares the staged diff against the build plan and reports only uncovered plan steps. (2026-08-05)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — In `--auto --plan-loop`, the resolve agent received a truncated task with no questions because `run_opencode_agent` did `shlex.quote(task)[:4095]` — a silent 4095-char cap (Python string slice, not bytes) guarding `ARG_M... (2026-08-04)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Added `demetra/tools/wiki.py` exposing `wiki_search` / `wiki_get_page` / `wiki_list_pages` so agents can consult `wiki/pages/*.md` before answering about past incidents. (2026-08-03)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — `mcp 2.0.0` (pulled by `uv-bump` in [[2026-08-03-auth-hardening-and-deps-bump]]) removed `@server.list_tools()`/`@server.call_tool()` decorators from low-level `Server`. (2026-08-03)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Generated a full favicon set (`.ico` + PNGs + PWA manifest) from `media/logo.svg` and wired it into `react/index.html`. (2026-08-03)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — Tightened API auth on three axes: (1) replaced ~10 hand-rolled cookie/`get_current_user` checks with `Depends(get_current_user_dep)`; (2) scoped session lookups by `user_id` so users can't read/stream/delete others' sess... (2026-08-03)
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — Replaced `passlib` `CryptContext` wrapper with direct `bcrypt` (dropped `passlib[bcrypt]`), made auth-cookie `SameSite` and CORS origins env-driven instead of hardcoded/wildcard, and bumped to `1.15.5` with broad depende... (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated `AGENTS.md` against the current codebase (wiki section added, f-string exception for `demetra/services/llm/prompt.py`, underscore-helper naming ban confirmed, deps moved to a `pyproject.toml`/`uv.lock` pointe... (2026-08-03)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implemented bcrypt password auth (signup/login/logout) alongside GitHub OAuth with JWT cookies and a React form. (2026-07-24)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — One row per workflow step is recorded from `opencode export` token totals. Odin DB (192 rows / 18 sessions) shows median `build` row ~15 M tokens (p99 40 M) vs `CONTEXT_COMPACTION_THRESHOLD` 100 k, and 25% NULL rows — bu... (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Added a "View History" button in `SessionArtifacts` that opens a modal timeline of `session_history` rows (step, timestamp, token breakdown). (2026-07-23)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigated the GitHub-only auth flow end-to-end and created Linear ticket **MNT-148** for adding email/password auth alongside it. (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — Revalidated `AGENTS.md` against code/wiki/git-log (4 fixes), deleted redundant `DOCS.md` (391 lines, fully duplicated), added an OpenCode command for automated AGENTS.md maintenance, and registered the LangSmith plugin i... (2026-07-23)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Post-merge cleanup for MNT-142 Warp theme plus infra updates: applied review feedback across 7 React components, hardened `bump_project_version` to `log+return None` instead of raising, added Makefile `user.signingkey`,... (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Three sessions covering the React frontend: mapped the component tree and flexbox layout, closed the sidebar–console gap into a single card (border/radius ownership moved to containers, `gap: 0`, `sidebar-footer` added),... (2026-07-22)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added `FEATURES` dict to `demetra/settings.py` gating `ruff`/`pytest` via `IS_RUFF_ENABLED`/`IS_PYTEST_ENABLED` (both default `False`), and made `demetra/workflows/lint.py:14-17, 31-34` check those flags alongside `is_pa... (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — MNT-136 hit `Max run attempts reached` after three identical crashes. A review finding containing `[/^\/admin/, ...]` was passed raw to `demetra.services.tui.print_message`, where Rich parsed `[/...]` as a closing tag an... (2026-07-21)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — Sessions with plan-agent questions no longer flip to `Failed` — they now enter an `Awaiting Input` state (stored as `step="awaiting_input"`). (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Raw ANSI escape sequences (`\x1b[31m` etc.) in logs rendered as garbled text. Fixed by adding stripping via regex `\x1b\[[0-9;]*[a-zA-Z]` at source and in the logging config, covering all handlers. (2026-07-20)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Behavior-preserving refactor of `setup_session_logging()` (`demetra/services/utils.py`) after the dedup fix in [[2026-07-15-duplicated-log-messages]]: dropped unused `logger` param (3 call sites), collapsed two handler l... (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Two causes for NULL `session_history` tokens: the local DB was missing migration `a2b3c4d5e6f7` (every INSERT failed silently), and on odin prod the migration was applied but all 38 rows still had NULL because `opencode... (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Code review of the `status`→`step` migration surfaced 4 findings — drifted duplicate step enum, `status`/`step` naming conflation in the API, stale hardcoded return in `upsert_pending_session`, and two undocumented diver... (2026-07-16)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Two listener bugs fixed: (1) `process_merge/rebase_notification` returned `bool` success but `demetra/listener.py` discarded it and always called `mark_notification_read` — failed enqueues were lost. (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Fixed a permanent stall where a run failing before plan save left `step='failed'` + empty `build_plan` → next run skipped planning (`step == 'initial'` gate) and exited forever. (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Two build-workflow logging bugs fixed: (1) `print_message()` lines duplicated in session logs because `setup_session_logging()` compared `Path` to `str` (always `False`), adding a second `FileHandler` to `tui_logger` wit... (2026-07-15)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — Added a fast deploy path: `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, with systemd units and nginx. Auth (GitHub/OpenCode) lives in `.env` via `EnvironmentFile`. (2026-07-07)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — Added automatic context-length tracking and compaction for OpenCode sessions. `session_history` records length after each step; when it exceeds `CONTEXT_COMPACTION_THRESHOLD` (default 100_000) the session is compacted vi... (2026-07-07)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — Rebuilt the session-log websocket from raw text to typed JSON (`{"type":"log"}` / `{"type":"status"}`) so the React app distinguishes log lines from status transitions. (2026-06-25)
- [Update project version](pages/2026-06-25-update-project-version.md) — Every feature/bugfix workflow now auto-bumps `pyproject.toml`; major bumps are manual. The bump is integrated into the workflow with rollback on failure. Tests added. (2026-06-25)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — Session artifacts now include a "View Linear Issue" link. A `linear_link` field was added to `sessions` (migration), set on first save when the Linear task is retrieved, returned by the API, and rendered in the React art... (2026-06-22)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — PRs now get a generated description instead of an empty body: a Groq-backed service summarises the completed work and the text is passed as the GitHub PR body. Tests added. (2026-06-22)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — Replaced `patch` DB mocks with fixtures/factories and local service calls with real invocations (third-party calls may stay mocked). (2026-06-15)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — Project creation was timing out because `run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to OpenCode agent/subprocess calls too, killing long operations like clone and build. (2026-06-10)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — Added markdown-to-HTML rendering for the build plan in the React app using the `marked` library. A new button in the build-plan modal parses the raw markdown with `marked` and replaces it with the rendered HTML. (2026-06-09)
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md) — Investigated what `LinearTicket.text` actually returns for resolved/unresolved comment threads, then used the findings to improve the Linear ticket renderer. (2026-06-09)
- [Build artifacts](pages/2026-06-09-build-artifacts.md) — Session artifacts — the PR link and the build plan — are now persisted and shown in the React app. (2026-06-09)
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md) — Added a `step` attribute to the `Session` model so an interrupted workflow can resume at the right step. (2026-06-08)
- [Project environment](pages/2026-06-08-project-environment.md) — Added per-project environment variables that are applied to every subprocess the supervisor spawns. (2026-06-08)
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md) — Added a `run_attempts` counter to the `sessions` table and a `MAX_RUN_ATTEMPTS` project setting (default 5, originally 3) so a Linear ticket cannot trigger an infinite chain of workflow runs. (2026-06-08)
- [Review summarization](pages/2026-06-04-review-summarization.md) — Review-agent findings are now summarized into one list by Groq + llama instead of being naively concatenated. (2026-06-04)
- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md) — Dropped the accumulated migration chain and replaced it with a single consolidated migration, updating the existing local database so `alembic upgrade` no longer errors. (2026-06-03)
- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md) — `uv run main.py --project-name mgallery --auto --plan-loop` made the OpenCode plan agent scan `/Users/alexander/www/m2/demetra` directly instead of the isolated process worktree, bloating the agent context with the whole... (2026-06-03)
- [Truncate session name](pages/2026-06-02-truncate-session-name.md) — Fixed a React layout bug where a long session name made the session list too tall and pushed the log console below it, breaking the intended left-right layout. (2026-06-02)
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md) — Automated the plan question round-trip: a separate resolve agent answers the plan agent's questions in `auto` mode instead of posting them to Linear. (2026-06-02)
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md) — Sessions can now be deleted entirely. A delete button sits near the clear button in the session log header; on click it sends a delete request to the API, which removes the session and all related objects (database recor... (2026-06-02)
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md) — Refactored and renamed the `hera` frontend app to `react`, normalizing the directory after `hera` had existed as an early scaffold. The rename touched the frontend directory, the Makefile, and docs. (2026-06-01)
- [Refactor API](pages/2026-06-01-refactor-api.md) — Split the too-long `demetra/api.py` into a `demetra/api/` package with routers grouped by route prefix (auth/github, projects, sessions, users, watcher, webhooks). (2026-06-01)
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md) — Added a basic MCP server as a single standalone `mcp_server.py` in the project root, using the `mcp` PyPI package. (2026-06-01)
- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md) — Removed the ticket-creation-from-text API added earlier (`demetra/api/tickets.py` + `demetra/services/ticket_provider.py`, the `/create-ticket` AI-extraction endpoint). (2026-05-25)
- [Async review](pages/2026-05-25-async-review.md) — Made the code-review step parallel: `run_review_agents` now runs all review agents asynchronously and merges their responses. (2026-05-25)
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md) — The session list now shows the task title instead of the truncated session id. The sessions API gained an endpoint with optional status filtering, sessions display a custom name when available with a fallback to the trun... (2026-05-22)
- [Link user, tasks and sessions](pages/2026-04-02-link-user-tasks-sessions.md) — Scoped Demetra's data to the logged-in user: every retrieved task and session is linked to its user, and tasks are retrieved only for projects linked to that user. (2026-04-02)
- [Project model and space](pages/2026-03-31-project-model-and-space.md) — Replaced the dict-mapped projects in settings with a `Project` database model linked to the logged-in user (`user_id`, `linear_project_id`, `name`, `repository_url`), including a migration that moved existing projects ou... (2026-03-31)
- [Add SQLAlchemy Core support](pages/2026-03-13-sqlalchemy-core-support.md) — Replaced raw SQL with SQLAlchemy Core (Core only, no declarative base): `demetra/services/database.py` now uses `Table`/`Column` objects. (2026-03-13)
- [Task plan summarization](pages/2026-03-11-task-plan-summarization.md) — Replaced the fragile string-search/trim plan extraction with a cleaned, summarized plan: `extract_plan` moved to `demetra/services/groq.py` and now runs a LangChain chain (Groq + llama, markdown output) over the plan out... (2026-03-11)
- [Separate Linear comments](pages/2026-03-11-separate-linear-comments.md) — Changed question posting so every found question becomes its own Linear comment instead of one aggregated comment, letting a human answer each one individually. (2026-03-11)

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### Workflow orchestration & agents (24 pages)

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
- [Review summarization](pages/2026-06-04-review-summarization.md) — 2026-06-04
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md) — 2026-06-02
- [Async review](pages/2026-05-25-async-review.md) — 2026-05-25
- [Task plan summarization](pages/2026-03-11-task-plan-summarization.md) — 2026-03-11

### MCP / integrations (13 pages)

- [MNT-205 — Revise merged environment: context.environment resolver](pages/2026-09-16-mnt-205-revise-merged-environment.md) — 2026-09-16
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
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md) — 2026-06-01

### React frontend / UI (13 pages)

- [MNT-204: Research result modal](pages/2026-09-14-research-plan-artifact.md) — 2026-09-14
- [MNT-193 — Mobile template for the React frontend](pages/2026-09-02-mobile-template-react-frontend.md) — 2026-09-02
- [MNT-192 Add edit button for env settings](pages/2026-08-31-mnt-192-env-edit-button.md) — 2026-08-31
- [MNT-188: Waitlist](pages/2026-08-28-mnt-188-waitlist.md) — 2026-08-28
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — 2026-08-25
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — 2026-08-03
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — 2026-07-22
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — 2026-06-22
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — 2026-06-09
- [Build artifacts](pages/2026-06-09-build-artifacts.md) — 2026-06-09
- [Truncate session name](pages/2026-06-02-truncate-session-name.md) — 2026-06-02
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md) — 2026-06-02
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md) — 2026-06-01

### Linear & GitHub integrations (13 pages)

- [Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications](pages/2026-09-14-listener-readline-limit-crash.md) — 2026-09-14
- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — 2026-08-28
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — 2026-08-18
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — 2026-08-10
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — 2026-08-05
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — 2026-07-16
- [Update project version](pages/2026-06-25-update-project-version.md) — 2026-06-25
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — 2026-06-22
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md) — 2026-06-09
- [Project environment](pages/2026-06-08-project-environment.md) — 2026-06-08
- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md) — 2026-05-25
- [Project model and space](pages/2026-03-31-project-model-and-space.md) — 2026-03-31
- [Separate Linear comments](pages/2026-03-11-separate-linear-comments.md) — 2026-03-11

### Sessions, status & resume (11 pages)

- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — 2026-08-25
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — 2026-07-23
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — 2026-07-23
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — 2026-07-21
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — 2026-07-16
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — 2026-07-16
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — 2026-06-25
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md) — 2026-06-08
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md) — 2026-06-08
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md) — 2026-05-22
- [Link user, tasks and sessions](pages/2026-04-02-link-user-tasks-sessions.md) — 2026-04-02

### Authentication & API security (8 pages)

- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — 2026-08-09
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — 2026-08-09
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — 2026-08-06
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — 2026-08-03
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — 2026-08-03
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — 2026-07-24
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — 2026-07-23
- [Refactor API](pages/2026-06-01-refactor-api.md) — 2026-06-01

### Deploy & infrastructure (6 pages)

- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — 2026-08-24
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — 2026-08-18
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — 2026-08-17
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — 2026-08-10
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — 2026-07-07
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — 2026-06-10

### Testing & tooling (6 pages)

- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — 2026-08-20
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — 2026-08-18
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — 2026-07-22
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — 2026-06-15
- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md) — 2026-06-03
- [Add SQLAlchemy Core support](pages/2026-03-13-sqlalchemy-core-support.md) — 2026-03-13

### Logging infrastructure (2 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — 2026-07-20
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — 2026-07-16

### Context, tokens & compaction (2 pages)

- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md) — 2026-06-03
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — 2026-07-07

### Docs, feature flags & release tooling (1 pages)

- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — 2026-08-21

### TUI & CLI (1 pages)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — 2026-07-21
