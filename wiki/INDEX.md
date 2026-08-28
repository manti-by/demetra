# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages

- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — The watcher daemon `process_tasks` created a pending session and enqueued a workflow but never moved the Linear ticket to `In Progress`; the status update lived only in `main.py` after `setup_workflow` succeeded, so a setup failure left the ticket stuck in TODO and re-picked every poll. `process_tasks` now moves a new task to `in_progress` the moment it accepts it (missing config / failed update log and continue). Tests added; full suite 920 passed; ruff / ty / bandit clean. (2026-08-28)
- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md) — The wiki INDEX read-modify-write was only serialized in-process: `_INDEX_LOCK` is an `asyncio.Lock()` (process-local) and the cross-process `flock` was taken only inside `_write_index_unlocked` — after the read — so two RQ workers in separate processes could both read the same `INDEX.md`, each append their own page entry, and the second `os.replace` clobbered the first (lost update). Added an `_index_lock` async context manager that holds the flock for the whole read-modify-write; all four mutating entry points (`write_index`, `prune_index_pages`, `patch_index`, `regenerate_by_topic`) now run under it, and the write helper no longer re-acquires the flock (which would have nested and deadlocked). 69 wiki tests pass; ruff / ty clean; verified with a two-subprocess concurrency repro. (2026-08-28)
- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) — Wiki page write was happening in `main.py`'s `finally` block after `commit_and_push` already committed/pushed, so it never reached the repo; moved the write into `commit_and_push` before commit, made `git_diff_facts` diff the working tree, and added a `"wiki"` `StepType` step. PR #103 deferred wiki failures so commit/push/PR still succeed; PR #106 (MNT-189) made wiki generation fully best-effort — failures log a warning only, with no `Awaiting Input` transition. (2026-08-25)
- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — Session-history endpoint now returns `{total, history}`; the modal shows a session-wide Total Tokens summary block. (2026-08-25)
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — Replaced every BE-waiting spinner in the React app with a reusable `Loader` component backed by `react/public/loader.svg`, and added a living Style Guide at `/styleguide` (linked from the burger menu) cataloging all UI primitives and composites. (2026-08-25)
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md) — The plan agent can exit 0 with empty stdout after a permission auto-rejection; `run_plan_step` fed that straight to the summarizer, which fabricated a fake plan sentence. Now guards on empty output and a missing `## Implementation Plan` header, raising `PlanError` and moving the ticket to Awaiting Input. 42 workflow tests pass. (2026-08-24)
- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — Fixed root-owned `.config/gh`/`.local/share/opencode` dirs (Docker root-creates bind-mount parents) by seeding them demetra-owned in the image and repairing ownership unconditionally every boot; also fixed a follow-on `setpriv: initgroups failed` after `USER demetra` by making the entrypoint user-aware. (2026-08-24)
- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — `bump_project_version` was bumping the major version for Epic-labeled tickets, contradicting the manual-only major rule; removed the `is_epic` branch so the function always bumps minor and preserves major. (2026-08-21)
- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — Fixed the test suite after the allowlist gate flipped its default from off to on (`IS_ALLOWLIST_ENABLED`, fail-closed); full suite 883 passed. (2026-08-20)
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md) — Found a critical missing `-o` operator in the entrypoint's `find` prune expression that silently disabled pruning for both the new `hosts.yml` mount and the existing `auth.json`; fixed before merge (PR #83). (2026-08-20)
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md) — MNT-151 build failures were initially attributed to the OpenCode workspace's $30/month spending limit (generic gateway 500); a same-day follow-up showed the identical error also comes from resuming a session bound to a cleanup-deleted worktree. Added a `BuildError` handler that posts a Linear comment and moves the ticket to Awaiting Input instead of silently reverting to TODO. Merged via PR #82. (2026-08-19)
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md) — Root cause confirmed: Demetra's persisted `sessions.session_id` pointed at an opencode session whose worktree cleanup had deleted; every retry resumed that dead session and 500'd. Fixed this instance by nulling the session row; the systemic code fix remains an open follow-up — still not implemented as of 2026-08-28. (2026-08-19)
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md) — Root-owned `demetra_app_data` volume caused `EACCES` on `~/.local/share/opencode`; fixed with a root entrypoint that chowns the home volume once per volume (marker-gated) and drops to `demetra` via `setpriv`. (2026-08-19)
- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — Split the `auth` and `linear` service facades into per-concern submodules, deleted the legacy `sys.meta_path` import-relocation shim, and changed review/PR-description LLM failures from silent empty returns to typed `ReviewError`/`PrDescriptionError` exceptions routed to Awaiting Input. Merged via PR #80. (2026-08-19)
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md) — Renamed the wiki write-side LLM-polish gate `budget_exceeded()` to `should_use_llm()` across the wiki subpackage and tests; behavior unchanged (still gated by `WIKI_LLM_BUDGET_FILES`/`_LINES`). (2026-08-19)
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — Classifies every workflow-runtime env var into project/user/system layers; MNT-170 (PR #80) executed the migration (Linear state/team ids and OpenRouter key/model → user env, `UV_PATH` → project env); step 5 test coverage still partial as of 2026-08-28 (`tests/test_settings_layers.py` covers Linear/OpenRouter only). (2026-08-18)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — Behavior-preserving refactor introducing `x-demetra-env`/`x-demetra-base`/`x-demetra-app` YAML anchors so the six app services stop duplicating ~20 lines each; shrunk `docker-compose.yaml` from 197 to 179 lines. (2026-08-18)
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — Replaced the Groq-backed LLM service with OpenRouter for plan extraction, review/PR-description generation, and wiki polish via a new `demetra/services/llm/openrouter.py` module; legacy `demetra/services/llm/groq.py` kept but unused. (2026-08-18)
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — Made `setup_test_db` autouse (tests were silently hitting the live `demetra` DB) and added a `console_only_logging` fixture (tests were writing into production log files); a same-day follow-up also fixed console runs leaving no session row on early plan failures. (2026-08-18)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — Code review of the mnt-164 branch found 7 blockers + 2 security findings; nearly all fixed on master in later sessions — historical record, current `docker compose up` is unblocked. (2026-08-17)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — Added a parallel `docker-compose.yaml` deployment path alongside the systemd `make deploy` path; validated end to end, surfacing several runtime fixes (pg18 mount path, LOG_PATH crash, psycopg-binary). Superseded in detail by the later anchor refactor. (2026-08-10)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — Extended per-project env into a three-layer OS→user-shared→project→step model, encrypted at rest via Fernet off `SECRET_KEY`, with per-project UV venv bootstrap and a React "Shared environment" screen with `.env` upload. (2026-08-10)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — Hardened four wiki-service edge cases surfaced by the fresh subpackage split (blank env paths, cluster scoring, cluster insertion at end-of-file, unreadable page files, answer-sweep preamble) and scoped revalidation commits to changed files only; optimized the three slowest test files, cutting the suite from ~13s to 729 passed in 4.60s. (2026-08-09)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — Added per-user `password_version` so JWTs minted before a password reset are rejected, fixed `authFetch`/`authenticatedFetch` to handle `Request` inputs correctly, plus 3 smaller fixes; full suite 739 passed. (2026-08-09)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — Restored cross-origin auth cookies in the React client (HIGH), plus 6 more findings across `env_get_int`, validate-agent, transaction atomicity, wiki dedup, and typed exceptions; full suite 737 passed. (2026-08-09)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — Found `env_get_list` returning `[]` instead of the default when unset, breaking CI's review-agent test and silently emptying `CORS_ALLOWED_ORIGINS`; fixed and merged as PR #70 on 2026-08-07. (2026-08-07)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — Split the monolithic 1254-line `demetra/services/wiki.py` into a `demetra/services/wiki/` package of six submodules behind a facade `__init__.py` re-exporting all 55 original symbols; all 728 tests pass. (2026-08-07)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — Applied all CodeRabbit findings on the MNT-155 allowlist PR (renamed underscore functions, hardened admin bypass to key off immutable GitHub id, seed-file validation/dry-run) and fixed 2 failing CI tests; full suite 619 passed. (2026-08-06)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — Added a read-only `validate-agent` step (now `wiki`'s sibling in `StepType`, sitting between `build` and `review`) that diffs the staged changes against the build plan and feeds missing items back into the build loop; also replaced 4095-char CLI-argument prompt truncation with stdin piping. Merged as `99b5880`. (2026-08-05)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — `gh pr create` failures used to silently revert the ticket to TODO with the branch already pushed and no explanation; added an `except PullRequestError` handler that posts a comment with the branch/compare URL and moves the ticket to Awaiting Input. Later extracted into `demetra/workflows/failure.py`'s shared `process_pr_failure`. (2026-08-05)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — `--auto --plan-loop` silently truncated the resolve-agent's prompt at a stale 4095-char cap, dropping the plan agent's questions. Removed the cap; later superseded entirely by PR #72's move to stdin piping. (2026-08-04)
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — Replaced passlib with direct bcrypt, made cookie SameSite and CORS origins env-configurable instead of hardcoded/wide-open, and refreshed dependencies; merged via PR #67. (2026-08-03)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — Consolidated ~10 duplicated auth checks into a single `get_current_user_dep`, scoped session lookups by `user_id`, fixed WebSocket close-code delivery, and tightened React credential/Origin handling; merged as PR #66/#67. (2026-08-03)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Generated a full favicon set (.ico + PNGs + PWA webmanifest) from `media/logo.svg` using `sharp` (cairosvg was unusable) and wired it into `react/index.html`; the `.ico` was hand-assembled from PNG payloads since `sharp` can't emit ICO. (2026-08-03)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — `mcp 2.0.0` removed the decorator-based `@server.list_tools()`/`@server.call_tool()` API; rewrote `demetra/mcp_server.py` against the new `on_list_tools`/`on_call_tool` constructor-callback API and verified end-to-end over stdio. (2026-08-03)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Implemented `demetra/tools/wiki.py` exposing `wiki_search`/`wiki_get_page`/`wiki_list_pages` MCP tools so agents can consult the session knowledge base; 28 tests, merged as PR #68. (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated `AGENTS.md` against the codebase and re-clustered `wiki/INDEX.md`'s "By topic" section; resolved two stale "not yet committed" claims by verifying PR #66/#67 had merged. (2026-08-03)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implemented password-based signup/login/logout alongside GitHub OAuth (bcrypt, JWT cookies, React form), then applied two passes of CodeRabbit review follow-ups (cookie-only auth, email normalization, `--resetpass` CLI, accessibility, header fallback chain). (2026-07-24)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigated the GitHub-only auth flow end-to-end and produced Linear ticket MNT-148 for adding email/password auth alongside GitHub OAuth. (2026-07-23)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — Corrected audit: compaction is live and non-cumulative (`build.py:100`), NULL rows were pipe-truncation (fixed, zero since); cache-read exclusion from the compaction decision is still an open recommendation. (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Original "View History" modal implementation; its response shape and auth signature have both since been superseded by later work (MNT-181, MNT-156). (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — Updated `AGENTS.md` to match the current codebase, deleted the redundant 391-line `DOCS.md`, added an `update-agents-file` OpenCode command for periodic revalidation, and registered the LangSmith plugin. (2026-07-23)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added a `FEATURES` dict gating `ruff`/`pytest` execution via `IS_RUFF_ENABLED`/`IS_PYTEST_ENABLED` (default off), now read via a shared `env_get_bool` helper; added settings + workflow tests covering all flag combinations. (2026-07-22)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Post-merge review cleanup for MNT-142, `bump_project_version` hardened to log+return None, Makefile/Playwright-MCP ops changes, and a green-accent palette refinement (typography moved to index.css, rainette green colors, table styles, RQ icon removal). (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Merged from three sessions: mapped the component tree/flexbox layout, closed the sidebar/console gap so they read as one card, added a typography baseline for rendered markdown, widened the build-plan modal, and added Playwright MCP to the toolchain. (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — A review finding containing `[/^\/admin/, ...]` crashed the workflow subprocess via an unescaped Rich markup parse, and `run_attempts` was incremented on every watcher call regardless of outcome. Fixed by escaping Rich markup in `print_message` and incrementing `run_attempts` only after an actual failure; `MAX_RUN_ATTEMPTS=5` default still current. (2026-07-21)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — Sessions no longer flip to `Failed` when the plan agent posts clarifying questions and moves the Linear ticket to Awaiting Input; stored as the `sessions.step = "awaiting_input"` enum value. (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Stripped ANSI escape sequences from log output at four points (utils helper, live_stream source, dictConfig filter, session log handlers) so colored subprocess output no longer garbles log files/viewers. (2026-07-20)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Code review of the `status`→`step` migration found a drifting duplicate step enum, a `status`/`step` naming conflation in the API, a stale hardcoded return value, and undocumented `ON CONFLICT` divergence; all 4 fixed, 473 tests pass. `StepType` has grown since (validate, awaiting_input, wiki) — now 12 values. (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — A run failing before a plan was saved locked sessions into an unplannable state; fixed by replanning on empty `build_plan` (not step), rejecting malformed Linear payloads as `LinearError`, and re-enabling session-id fallback. 472 tests pass. (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Root cause: `opencode export` truncates at 64KB over a subprocess pipe; fixed via `run_command_to_file`, still in effect at its current module path. (2026-07-16)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Refactored `setup_session_logging()` (behavior-preserving): dropped the unused `logger` param, collapsed duplicate handler loops into one lookup, removed dead formatter fallbacks; 36→27 lines, 472 tests pass. (2026-07-16)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Fixed the listener marking notifications as read even when enqueue failed, and added a `listener_attempts` counter (`MAX_LISTENER_ATTEMPTS`, now 5) that breaks the retry loop after repeated failures. (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Fixed a `Path == str` comparison that always evaluated False, causing a duplicate `FileHandler` and doubled `print_message` output, and fixed the build agent's stdout being discarded instead of logged. (2026-07-15)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — Added `session_history` tracking plus `/compact` at a 100k-token threshold; briefly disabled (MNT-145) then re-enabled the same day on a non-cumulative metric, live today. (2026-07-07)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — Built a `Makefile` `deploy` target plus `configs/bootstrap.sh` for first-time setup, backed by systemd units and nginx; Docker is the alternative path. (2026-07-07)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — Typed `{type, data}` JSON envelope for logs/status over the session websocket; the payload key was later renamed `status`→`step` to track the session-model refactor. (2026-06-25)
- [Update project version](pages/2026-06-25-update-project-version.md) — Added automatic minor-version bumping in `pyproject.toml` on every feature/bugfix workflow with rollback on failure; the original implementation actually also bumped major on Epic tickets until MNT-176 removed that branch. (2026-06-25)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — Persists and surfaces the originating Linear ticket link in session artifacts. (2026-06-22)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — PRs created from a completed feature get a real LLM-generated description instead of an empty/placeholder body; the generator now lives in `demetra/services/llm/openrouter.py` and raises `PrDescriptionError` on failure. (2026-06-22)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — Replaced `patch` mocks with real fixtures/factories across the suite, added Docker build targets for amd64/ARM64, filtered trivial "no issue" review responses, and bumped to 1.13.0. (2026-06-15)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — `run_command` applied a short 120s timeout to OpenCode calls too, killing clone/build; renamed `SHELL_TIMEOUT_MS` to `SUBPROCESS_TIMEOUT` (seconds, default 1800) and removed the explicit short timeout from OpenCode callers. (2026-06-10)
- [Build artifacts](pages/2026-06-09-build-artifacts.md) — Persists and renders `pr_link` and `build_plan` as a session artifact block. (2026-06-09)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — Added markdown-to-HTML rendering for the build plan modal using the `marked` library. (2026-06-09)
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md) — Investigated what `LinearTicket.text` returns for comment threads and used it to improve the ticket renderer: filter by state, branch/labels on the issue list, resolved status/timestamps/authors on comments, nested replies. (2026-06-09)
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md) — Added a `step` attribute to `Session` so an interrupted workflow resumes at the right step; the 6-value vocabulary documented here is a historical snapshot — `StepType` now has 12 values including `validate`, `awaiting_input`, and `wiki`. (2026-06-08)
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md) — Added a `run_attempts` counter and `MAX_RUN_ATTEMPTS` cap (originally default 3, now default 5) so a ticket can't trigger unbounded workflow runs; increment semantics later corrected to count only actual failures. (2026-06-08)
- [Project environment](pages/2026-06-08-project-environment.md) — Added per-project environment variables (new `Environment` model) applied to every subprocess the supervisor spawns, cached on the `Project` dataclass. (2026-06-08)
- [Review summarization](pages/2026-06-04-review-summarization.md) — Review-agent findings are summarized into one deduplicated list by an LLM call instead of naive concatenation; `merge_review_results` has since been fully removed in favor of `summarize_review()`. (2026-06-04)
- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md) — Squashed the drifted Alembic migration chain into one consolidated migration, updated DB connection init to modern config patterns, and made `projects.repository_url` required. (2026-06-03)
- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md) — Plan/build/review/resolve agent subprocesses weren't inheriting the isolated worktree as their `cwd`, so they scanned the whole supervisor repo instead of the per-ticket worktree; fixed by setting `cwd` explicitly for every agent subprocess. (2026-06-03)
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md) — Automated the plan question round-trip via a dedicated resolve agent in `auto` mode instead of posting to Linear; `--plan-loop` loops plan/resolve with `MAX_PLAN_ATTEMPTS` (default 30, still current). (2026-06-02)
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md) — Full session delete (DB rows + log files) with an auto-refreshing session list. (2026-06-02)
- [Truncate session name](pages/2026-06-02-truncate-session-name.md) — Fixed a layout bug where long session names pushed the log console below the sidebar; the session-item title now truncates via CSS following the existing `.session-plan` fixed-width pattern. (2026-06-02)
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md) — Renamed the `hera` frontend scaffold to `react`, updated the Makefile/docs, tightened GitHub auth validation, and removed legacy FastAPI docs. (2026-06-01)
- [Refactor API](pages/2026-06-01-refactor-api.md) — Split the monolithic `demetra/api.py` into a `demetra/api/` package with per-prefix routers, landing GitHub OAuth, project CRUD, session tracking, websocket log streaming, and user API-key management in one bundle. (2026-06-01)
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md) — Added a standalone MCP server exposing filesystem and PostgreSQL-only database tools with no auth; filesystem tools were removed the next day, and the server was later moved to `demetra/mcp_server.py` running over stdio. (2026-06-01)
- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md) — Deleted the AI-text-extraction `/create-ticket` endpoint and its provider in favor of the Linear-native ticket flow. (2026-05-25)
- [Async review](pages/2026-05-25-async-review.md) — Made the code-review step parallel (`run_review_agents` runs all agents concurrently), fixed `merge_review_results` to handle `None` stdout/stderr, and prevented empty commits by validating staged changes. (2026-05-25)
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md) — Session list shows the task title with a fallback to the truncated id; the status filter param was later renamed to `step`. (2026-05-22)

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### Workflow orchestration & session lifecycle (14 pages)

- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md)
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md)
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md)
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md)
- [Plan step completion attribute](pages/2026-06-08-session-step-attribute.md)
- [Max run attempts for a ticket](pages/2026-06-08-max-run-attempts-for-a-ticket.md)
- [Add Plan loop to resolve questions](pages/2026-06-02-plan-loop-resolve-questions.md)

### Sessions, history & tokens (10 pages)

_(session-history-modal also sits in React frontend / UI.)_

- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md)
- [Session History Modal](pages/2026-07-23-session-history-modal.md)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md)
- [Build artifacts](pages/2026-06-09-build-artifacts.md)
- [Add delete button for a session](pages/2026-06-02-delete-session-button.md)
- [Use task title for session listing](pages/2026-05-22-task-title-session-listing.md)

### React frontend / UI (8 pages)

_(session-history-modal also sits in Sessions, history & tokens, its primary home.)_

- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md)
- [Session History Modal](pages/2026-07-23-session-history-modal.md)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md)
- [Truncate session name](pages/2026-06-02-truncate-session-name.md)
- [Refactor frontend app](pages/2026-06-01-refactor-frontend-app.md)

### Authentication & API security (7 pages)

_(allowlist-review-fixes and apply-pr75-coderabbit-findings also sit in Code-review findings application.)_

- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md)
- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md)

### Docker & deploy (7 pages)

- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md)
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md)
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md)

### Wiki & knowledge base (7 pages)

- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md)
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md)

### Settings, environment & subprocess (5 pages)

- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md)
- [Project environment](pages/2026-06-08-project-environment.md)

### LLM pipeline & review agents (4 pages)

- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md)
- [Review summarization](pages/2026-06-04-review-summarization.md)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md)
- [Async review](pages/2026-05-25-async-review.md)

### Code-review findings application (3 pages)

_(apply-pr75-coderabbit-findings and allowlist-review-fixes also sit in Authentication & API security.)_

- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md)

### Logging infrastructure (3 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md)

### Docs, versioning & wiki governance (3 pages)

- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md)
- [Update project version](pages/2026-06-25-update-project-version.md)

### MCP server (2 pages)

- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md)
- [Add MCP server for the project](pages/2026-06-01-add-mcp-server.md)

### Service architecture & refactoring (2 pages)

- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md)
- [Refactor API](pages/2026-06-01-refactor-api.md)

### Testing & CI (2 pages)

- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md)

### Linear & GitHub integrations (3 pages)

- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md)
- [Check Linear ticket text](pages/2026-06-09-check-linear-ticket-text.md)

### Database & migrations (1 page)

- [Fix and squash migrations](pages/2026-06-03-fix-squash-migrations.md)

### Context & agent scanning (1 page)

- [Context bloating — agents scan repo root instead of worktree](pages/2026-06-03-context-bloating.md)

### Decommissioned (1 page)

- [Remove ticket API](pages/2026-05-25-remove-ticket-api.md)
