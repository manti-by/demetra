# Demetra Wiki - Index

Session knowledge base for the Demetra project - one Markdown page per debugging
chase, investigation, code review, or set of changes. See [README.md](README.md) for conventions
and [TEMPLATE.md](TEMPLATE.md) for the page template. New pages are added and updated automatically
by the plugin.

## Pages
_Newest first._

- [CH-12: Session list order](pages/2026-11-12-ch-12-session-list-order.md) — Implementation of CH-12: Session list order (2026-11-12)
- [Unified Task model with Linear and Chat subtypes](pages/2026-11-11-mnt-312-unified-task-model.md) — Linear tickets and chat sessions are now driven by one generic `Task` entity with one generic `Message` history: new `tasks`/`messages` tables beside the workflow state in `sessions`, `LinearTask`/`Chat` and `LinearComment`/`ChatMessage` as subtypes, `chats` shrunk to a subtype row, the FK-less duplicate `chat_messages.session_task_id` dropped, and a `--linear-sync` CLI that backfills every issue of the linked Linear projects with its comments. (2026-11-11)
- [CH-10: PR description for Chat sessions](pages/2026-11-10-ch-10-pr-description-for-chat-sessions.md) — Chat-session PR descriptions are unwrapped from markdown code fences before posting: `_unwrap_pr_body` in `demetra/workflows/cleanup.py` strips surrounding fences... (2026-11-11)
- [MNT-309: Chat Template](pages/2026-11-10-mnt-309-chat-template.md) — Chat templates for new chats: Markdown files in `demetra/templates/chat/`, a public `GET /api/v1/chat-templates` endpoint returning every template's content, and a selector in `NewChatPage.tsx` whose... (2026-11-10)
- [MNT-308: Lint and test erorrs](pages/2026-11-10-mnt-308-lint-error-extraction.md) — Lint and test failures are now summarised before they reach the build agent: a new `extract_errors` service (OpenRouter prompt `demetra/prompts/extract_errors.md`) parses ruff/pytest output into a ded... (2026-11-10)
- [Durable review-round budget in sessions.review_attempts](pages/2026-11-10-durable-review-attempts-budget.md) — The build loop's review budget was a local variable, so every workflow restart re-granted a fresh `MAX_ATTEMPTS["review"]` rounds; applied review rounds are now counted in a durable `sessions.review_a... (2026-11-10)
- [MNT-298 research agent ECONNRESET — local opencode server thrash](pages/2026-11-06-mnt-298-research-econnreset-root-cause.md) — Proved the `ECONNRESET` is a local opencode CLI↔server event-stream drop (`event stream disconnected`, `role=cli`), not a DeepSeek failure: concurrent `opencode run` invocations replace one `service.j... (2026-11-06)
- [MNT-277: Do not remove git worktree for sessions](pages/2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions.md) — Chat sessions no longer lose their worktree: the cleanup path keeps the branch and worktree for chat sessions instead of removing them, so a re-run can resume the same working state. (2026-11-06)
- [CH-6: Markdown renderer](pages/2026-11-06-ch-6-markdown-renderer.md) — Chat blocks (descriptions, build plans, research plans, questions, user messages) now render markdown instead of plain text, through a shared `react/src/components/MarkdownContent.tsx` component that... (2026-11-06)
- [CH-5: Delete chat button](pages/2026-11-06-ch-5-delete-chat-button.md) — A delete button for chat sessions, matching the Linear session delete UI: it renders only when a handler is supplied, calls it with the current task id, and reuses the same styling and frontend tests. (2026-11-06)
- [Agent ECONNRESET network errors — root cause](pages/2026-11-06-agent-econnreset-network-investigation.md) — Traced the CH-1–CH-4 agent `ECONNRESET` failures: idle-hold tests (Google stays alive 80s; DeepSeek closes at 30s, Cloudflare at 15s) plus streaming and a 10 MB download proved the mid-stream resets a... (2026-11-06)
- [Chat session list and rerun semantics](pages/2026-11-04-chat-session-list-and-rerun.md) — Three-row session items (`C`/`L` type + step + time, title, project chip + labels) with `project_name` joined into the sessions and chats APIs; feedback loops are now counted from `session_history` (`... (2026-11-04)
- [MNT-276: ECONNRESET retry for agents](pages/2026-11-03-mnt-276-econnreset-retry-for-agents.md) — `run_opencode_agent` retries transient network failures (`ECONNRESET`, `socket hang up`, `ETIMEDOUT`, …) with exponential backoff up to `MAX_AGENT_NETWORK_ATTEMPTS` (5), resuming the failed attempt's... (2026-11-03)
- [CH-2: Single (unified) session view](pages/2026-11-03-ch-2-single-unified-session-view.md) — Chat sessions open in the session log instead of a separate `/chats/:taskId` window: `ChatPanel` was extracted out of `ChatPage` (which is now a thin wrapper) and rendered above `LogConsole` in `App.t... (2026-11-03)
- [MNT-260: Session calls to openrouter](pages/2026-10-27-mnt-260-openrouter-call-history.md) — Every OpenRouter call now writes a `kind='llm_call'` `session_history` row (`record_llm_call`), carrying token usage extracted from the `AIMessage` response metadata plus model/agent/cost; `task_id` t... (2026-10-27)
- [Session history — one row per agent invocation](pages/2026-10-25-session-history-per-invocation-rows.md) — The history modal read `build → validate → validate → validate → review`: `record_agent_invocation` upserted `kind='invocation'` rows per `(task, session, step)` and accumulated the delta, so the buil... (2026-10-25)
- [Session history — cached bundle and MCP tool usage](pages/2026-10-25-session-history-mcp-tool-usage.md) — "Total Cost missing" was a stale browser bundle (API returned `total.cost`, served JS already had the cell); the real gap was MCP tool usage: opencode v2 code mode runs MCP tools inside the `execute`... (2026-10-25)
- [Session history — session cost total and failure reasons](pages/2026-10-25-session-history-cost-and-failure-reasons.md) — Two UI gaps in the session-history timeline closed: the totals block now sums per-invocation `cost` into a new `total["cost"]` rendered as a "Total Cost" cell, and `failed`/`awaiting_input` cards show... (2026-10-25)
- [MNT-258: Tool usage stats](pages/2026-10-25-mnt-258-tool-usage-stats.md) — Added the `session_tool_usage` table (FK to `agent_sessions`) and surfaced per-tool call counts through `SessionExport`, the history API and the React history modal; a per-invocation `invoked_at` epoc... (2026-10-25)
- [Fix the MCP database tools — missing env and broken SQL](pages/2026-10-25-mcp-db-tools-env-sql.md) — Every Demetra MCP database tool returned `Error: Database operation failed`: the MCP child of `opencode serve --service` had no `DB_*` in its environment while `settings.DATABASE` reads only `os.envir... (2026-10-25)
- [OpenCode v2 migration — CLI ground truth, the compaction no-op, and the corrected MNT-251 plan](pages/2026-10-16-opencode-v2-session-token-accounting.md) — v2 CLI ground truth where the then-floating install hovered: production ran opencode **1.18.30** where everything Demetra passed still worked, so MNT-246's 6.4× inflation figures described live produc... (2026-10-16)
- [MNT-251 — Rebuild agent session attribution and token accounting for opencode v2](pages/2026-10-16-mnt-251-session-attribution-accounting.md) — Implemented the full two-phase MNT-251 build in one branch. **Phase 1:** opencode is now version-aware (no `--dir`; `session export` on v2 / `export` on 1.x, still file-backed; both forms tried when t... (2026-10-16)
- [MNT-245: Empty session history](pages/2026-10-16-mnt-245-empty-session-history.md) — Why `validate`/`review`/`research` rendered as empty cards: two independent writers (every step transition wrote a guaranteed-empty row; token rows came from a path only plan/build/completed/failed ca... (2026-10-16)
- [MNT-234: Isolate session context](pages/2026-10-16-mnt-234-isolate-session-context.md) — Research into per-agent session isolation: only build resumes plan's session, and the plan→build pair should stay connected via `--fork` (the literature-backed middle ground). Surfaces the plan-loop s... (2026-10-16)
- [Replace the wiki MCP tool with WI and refactor demetra/tools](pages/2026-10-15-replace-wiki-mcp-tool-with-wi.md) — The in-repo wiki MCP tool (`wiki_search`/`wiki_get_page`/`wiki_list_pages`) is retired in favour of the external **WI** MCP server, and the rest of `demetra/tools` was restructured onto `manti-by/odin... (2026-10-15)
- [Session state flow: completed chain, feedback loops, research chain](pages/2026-10-12-session-state-flow-feedback-loops.md) — `completed` now completes every `SessionStateFlow` node via a new `finalSteps` flag so the GitHub node stops blinking; the free-floating curved feedback arrows became square SVG brackets measured from... (2026-10-12)
- [MNT-244: Session state animation](pages/2026-10-12-session-state-animation.md) — Added a `SessionStateFlow` React component that animates the live session step above the log console, updated over the session websocket. Backend gains a `sessions.is_research` column (migration `b7c8... (2026-10-12)
- [Review agent models bypass the environment layers](pages/2026-10-12-review-models-env-resolution.md) — `OPENCODE_REVIEW_MODELS` was the last agent setting read straight from `settings.py`: review is the only agent with an N-model fan-out, so both env-rework passes skipped it and the plural key never ma... (2026-10-12)
- [BM25 ranking for the wiki and docstring MCP tools](pages/2026-10-09-bm25-search-for-mcp-tools.md) — `wiki_search` and `docstring_search` now rank with BM25F over cached token counts, fixing substring matching (`log` matched `logging`), IDF and length normalization; the wiki tool gained the mtime+siz... (2026-10-09)
- [LLM-authored wiki pages and normalized frontmatter](pages/2026-10-08-llm-authored-wiki-pages.md) — Wiki pages are now always LLM-authored: `render_wiki_page`'s deterministic scaffold is replaced by `compose_wiki_page`, the `should_use_llm` budget gate and `WIKI_LLM_BUDGET_*` settings are deleted, a... (2026-10-08)
- [Unify subprocess env on SessionEnvironment](pages/2026-10-06-unify-subprocess-env-on-session-environment.md) — The legacy `env: dict[str,str]` parameter is gone from `run_command`/`run_command_to_file` and every git/gh/quality/wiki/agent helper: each layer now takes `environment: SessionEnvironment`, and `Sess... (2026-10-06)
- [MNT-232: Update research flow](pages/2026-10-05-mnt-232-update-research-flow.md) — Research now links the created ticket back to the originating ticket as `related` (retried on transient failures), moves the source ticket to In Review instead of Awaiting Input, and writes the `resea... (2026-10-05)
- [MNT-228: Intermediate history states](pages/2026-09-30-mnt-228-intermediate-history-states.md) — Session history now records intermediate step transitions (step + timestamp rows via `update_session_step(..., session_id=...)`) without a schema migration, and the frontend history UI shows localized... (2026-09-30)
- [Forward LangSmith env vars from host to containers](pages/2026-09-28-compose-langsmith-host-env.md) — `docker-compose.yaml` forwards `LANGSMITH_TRACING`/`_ENDPOINT`/`_API_KEY`/`_PROJECT` into every container via the `x-demetra-env` anchor using `${VAR:-default}` host interpolation (shell outranks `--e... (2026-09-28)
- [MNT-225: Add copy button](pages/2026-09-27-mnt-225-add-copy-button.md) — Added a "Copy" button to the build plan modal footer that writes the raw markdown via `navigator.clipboard.writeText()`, with clipboard feature detection and 1.5s "Copied!" feedback. A pending copy is... (2026-09-27)
- [MNT-219: Session log autoscroll](pages/2026-09-24-mnt-219-session-log-autoscroll.md) — Session log now autoscrolls to the latest records on new logs or session change (`LogConsole` `useEffect` on `taskId`+`logs` with `{ block: "end" }`); CSS smooth scroll off on `.log-content`; tests ad... (2026-09-24)
- [Bake opencode agents and skills into the Docker image](pages/2026-09-18-dockerfile-opencode-agents-skills.md) — Dockerfile now copies `.opencode/agents/` and `.opencode/skills/` to `/home/demetra/.config/opencode/` with demetra ownership and 755/644 modes, plus .dockerignore re-includes. (2026-09-18)
- [MNT-205 — Revise merged environment: context.environment resolver](pages/2026-09-16-mnt-205-revise-merged-environment.md) — The implementation standardized methods for resolving agent models, Linear settings, and OpenRouter settings by introducing a single SessionEnvironment resolver. (2026-09-16)
- [MNT-204: Research result modal](pages/2026-09-14-research-plan-artifact.md) — Added "View Research Plan" link + modal mirroring the build-plan artifact — new `sessions.research_plan` column, Session persistence, API exposure, and `SessionArtifacts` UI with markdown toggle. (2026-09-14)
- [OpenCode agent system prompts — permission hardening, injection guards, and merge/rebase semantics](pages/2026-09-14-opencode-agent-prompts-hardening.md) — Hardened all 7 `.opencode/agents/*.md` prompts (only `research-agent.md` had `description`/`permission` before). (2026-09-14)
- [Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications](pages/2026-09-14-listener-readline-limit-crash.md) — The GitHub notification listener (`demetra/listener.py`) has never processed a single notification: the log shows 2792 `Error polling GitHub notifications` tracebacks and **zero** `Processing notifica... (2026-09-14)
- [MNT-203: Create related ticket for research](pages/2026-09-11-mnt-203-create-related-ticket-for-research.md) — Research workflow now creates a related Linear ticket instead of posting a comment on the source ticket. New ticket inherits project, priority, and state (`PRD`), with `Feature` plus source `Backend`/... (2026-09-11)
- [MNT-200: Update research loop](pages/2026-09-10-mnt-200-update-research-loop.md) — Research loop now persists the extracted report to new `sessions.research_report` column and uses a new `researched` StepType (navy-blue badge). Added migration, StepType/Session updates, and React/CS... (2026-09-10)
- [OpenCode Reasoning Token History Is Zero](pages/2026-09-08-opencode-reasoning-token-zero.md) — Demetra persists `reasoning` from `opencode export` unchanged — zeros originate in OpenCode, not in API/frontend/DB. (2026-09-08)
- [MNT-171: Docstring MCP search](pages/2026-09-08-docstring-mcp-search.md) — MCP server now exposes `docstring_search`/`docstring_get`/`docstring_list` — ranked qualified names + snippets, full docstring by name, and catalog dump. (2026-09-08)
- [Review findings cleanup — v1.16.7..HEAD two-axis review](pages/2026-09-02-review-findings-cleanup.md) — Standards/Spec review of changes since `v1.16.7` then applied findings: removed dead code, extracted four duplication clusters (BE 202-response, encrypted-secret resolution, review-thread formatting,... (2026-09-02)
- [MNT-193 — Mobile template for the React frontend](pages/2026-09-02-mobile-template-react-frontend.md) — Mobile-responsive template for `react/src` per MNT-193 (MNT-174 mockups adapted to `SessionSidebar`/`SessionList`/`LogConsole`/`Header`). (2026-09-02)
- [MNT-177 research loop — research agent, workflow and settings](pages/2026-09-01-mnt-177-research-loop.md) — Added Research loop: tickets with `Research` label run a read-only `research-agent` (wiki + web validation) that extracts `## Research Report`, posts it as a Linear comment, and moves the ticket to `A... (2026-09-01)
- [MNT-192 Add edit button for env settings](pages/2026-08-31-mnt-192-env-edit-button.md) — Added pencil edit button to every env var row in `EnvSettings` and `SharedEnvSettings` modals with inline edit, rename via delete+re-add, duplicate-key guard, sorted display, and backend preservation... (2026-08-31)
- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — Watcher created a pending session and enqueued a workflow for TODO tickets but never moved the Linear ticket to `In Progress` itself — that update lived only in `main.py` after `setup_workflow` succee... (2026-08-28)
- [MNT-188: Waitlist](pages/2026-08-28-mnt-188-waitlist.md) — Blocked users can join a waitlist (HTTP 202) and admins approve entries via CLI to promote them to the allowlist. (2026-08-28)
- [MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation](pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md) — MNT-177 retried 6× on 2026-08-28 and never left the plan step. Dominant cause (3/6 runs) was OpenRouter 403 on `meta/muse-spark-1.2` requiring 18+ attestation; 2 runs truncated by auto-rejected `read... (2026-08-28)
- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md) — Wiki INDEX read-modify-write was only in-process serialized: `_INDEX_LOCK = asyncio.Lock()` plus `flock` taken only inside `_write_index_unlocked` after the read. (2026-08-28)
- [Workflow proceeds to review after ticket moved to Awaiting Input](pages/2026-08-28-awaiting-input-workflow-continues-to-review.md) — Same-run halt after posting questions works (`move_to_awaiting_input` raises `AutoCancelledError`), but the signal is not durable: the questions-run persists `build_plan` before posting questions and... (2026-08-28)
- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) — Wiki pages were written in `main.py`'s `finally` after `commit_and_push` committed/pushed, targeting the main checkout (`WIKI_ROOT = BASE_PATH / "wiki"`) not the worktree — so `wiki/pages/*.md` never... (2026-08-25)
- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — Added a session-wide **Total Tokens** summary to the history modal. `GET /api/v1/sessions/{task_id}/history` now returns `{"total": {...}, "history": [...]}` via `_compute_total_tokens` in `demetra/ap... (2026-08-25)
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — Replaced all backend-waiting spinners with `react/public/loader.svg` (olive #788860) via a reusable `Loader` component, and added a living Style Guide at `/styleguide` linked from the burger menu cata... (2026-08-25)
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md) — Workflow showed `No implementation plan was provided in the plan output` as the build plan — a hallucination by the `extract_plan` LLM given empty stdout. (2026-08-24)
- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — `gh auth` inside containers failed with `failed to write config after migration: open /home/demetra/.config/gh/config.yml: permission denied`. (2026-08-24)
- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — `bump_project_version` incorrectly bumped major for Epic-labeled tickets (`1.x.y → 2.0.0`); rule is major is manual-only. (2026-08-21)
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md) — Reviewed working-tree changes adding `gh` auth to Docker: bind mount `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` and matching `find -prune` entry. (2026-08-20)
- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — MNT-173 flipped the allowlist gate from default-off (`ALLOWLIST_ENABLED`/`is_allowlist_enabled()`) to default-on `IS_ALLOWLIST_ENABLED = env_get_bool(..., True)` (fail-closed), leaving 12 failures + 2... (2026-08-20)
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md) — Worker failed at plan step: `EACCES: permission denied, mkdir '/home/demetra/.local/share/opencode/repos'` — the `demetra_app_data` volume at `/home/demetra` (`docker-compose.yaml:15`) had root-owned... (2026-08-19)
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md) — Renamed wiki gate `budget_exceeded()` → `should_use_llm()` across `demetra/services/wiki/` and `tests/test_wiki.py`. (2026-08-19)
- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — On the MNT-170 branch (merged via PR #80, 2026-08-19), the `auth` and `linear` monolithic facades were split into per-concern submodules behind `__init__.py` facades and the `sys.meta_path` relocation... (2026-08-19)
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md) — After the spending limit was raised, MNT-151 kept failing with `UnknownError: Unexpected server error (err_...)` — not the limit but a stale `sessions.session_id` (`ses_fe96234f1ffeADBso4qFrnzE0Y`) bo... (2026-08-19)
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md) — MNT-151 builds failed ~4s after "Running BUILD agent" with `UnknownError: Unexpected server error (err_...)` exit 1. (2026-08-19)
- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — Tests wrote into the production `demetra` DB and spammed `/var/log/demetra/demetra.log` because `setup_test_db` wasn't autouse and `runtime/tui.py` installs a `FileHandler` at import. (2026-08-18)
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — Replaced Groq with OpenRouter for all LLM summarization (plan extraction, review, ticket breakdown, wiki polish, PR descriptions) via a single `build_llm()` factory over `langchain-openai` `ChatOpenAI... (2026-08-18)
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — DRY refactor of `docker-compose.yaml`: six `mantiby/demetra:latest` services repeated ~20 identical lines; introduced three YAML anchors (`x-demetra-env`, `x-demetra-base`, `x-demetra-app`) merged via... (2026-08-18)
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — Classified every workflow env var in `demetra/settings.py` into three layers — **project** (`project_environment`), **user** (`user_environment` `scope='user'`), or **system** (stays in `settings.py`,... (2026-08-18)
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — Review of `mnt-164-docker-compose` found the previously-verified Docker setup regressed with multiple blockers preventing boot — missing source copy, stale venv path, `WORKDIR` typo, `.keys/` baked in... (2026-08-17)
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — Extended per-project env into three layers — OS (allowlisted) → user-shared → project → step (last writer wins). (2026-08-10)
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — Added a parallel `docker-compose.yaml` path running the full stack (Postgres, Redis, api, 4 workers, watcher, listener, rq-dashboard, one-shot React build) on `mantiby/demetra`. Systemd `make deploy`... (2026-08-10)
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — Hardened four wiki-service edge cases from the subpackage split (blank env paths, cluster scoring, last-header insertion, unreadable files, `answer_sweep` preamble) and scoped revalidation commits to... (2026-08-09)
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — Applied 5 CodeRabbit findings on PR #75: versioned JWTs via `password_version` to close the post-snapshot race, fixed `Request`-aware `authFetch` origin guard, rejected negative `env_get_int` defaults... (2026-08-09)
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — Applied all 7 findings from post-refactor review (`CODE_REVIEW_FINDINGS.md`, `v1.15.4..HEAD`): restored cross-origin auth cookies, rejected negative `env_get_int`, gated validate-agent on `Plan step N... (2026-08-09)
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — Split monolithic `demetra/services/wiki.py` (1254 lines) into `demetra/services/wiki/` with six submodules behind a facade `__init__.py` re-exporting all 55 symbols. (2026-08-07)
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — PR #70 was MERGEABLE (UNSTABLE while CI failed). Root cause: `env_get_list` in `demetra/services/utils.py:249` returned `[]` instead of the default when the env var was unset, so CI (without `OPENCODE... (2026-08-07)
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — Applied all actionable CodeRabbit findings on PR #71 (MNT-155 allowlist): de-prefixed functions, moved flag to `demetra/settings`, hardened admin bypass to immutable GitHub ID, validated seed-file ent... (2026-08-06)
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — `gh pr create` failures after a successful push previously reverted the ticket to TODO with no Linear trace. (2026-08-05)
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — Added a read-only `validate-agent` between build and review that compares the staged diff against the build plan and reports only uncovered plan steps. (2026-08-05)
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — In `--auto --plan-loop`, the resolve agent received a truncated task with no questions because `run_opencode_agent` did `shlex.quote(task)[:4095]` — a silent 4095-char cap (Python string slice, not by... (2026-08-04)
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — Added `demetra/tools/wiki.py` exposing `wiki_search` / `wiki_get_page` / `wiki_list_pages` so agents can consult `wiki/pages/*.md` before answering about past incidents. (2026-08-03)
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — `mcp 2.0.0` (pulled by `uv-bump` in [[2026-08-03-auth-hardening-and-deps-bump]]) removed `@server.list_tools()`/`@server.call_tool()` decorators from low-level `Server`. (2026-08-03)
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — Generated a full favicon set (`.ico` + PNGs + PWA manifest) from `media/logo.svg` and wired it into `react/index.html`. (2026-08-03)
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — Tightened API auth on three axes: (1) replaced ~10 hand-rolled cookie/`get_current_user` checks with `Depends(get_current_user_dep)`; (2) scoped session lookups by `user_id` so users can't read/stream... (2026-08-03)
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — Replaced `passlib` `CryptContext` wrapper with direct `bcrypt` (dropped `passlib[bcrypt]`), made auth-cookie `SameSite` and CORS origins env-driven instead of hardcoded/wildcard, and bumped to `1.15.5... (2026-08-03)
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — Revalidated `AGENTS.md` against the current codebase (wiki section added, f-string exception for `demetra/services/llm/prompt.py`, underscore-helper naming ban confirmed, deps moved to a `pyproject.to... (2026-08-03)
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — Implemented bcrypt password auth (signup/login/logout) alongside GitHub OAuth with JWT cookies and a React form. (2026-07-24)
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — One row per workflow step is recorded from `opencode export` token totals. Odin DB (192 rows / 18 sessions) shows median `build` row ~15 M tokens (p99 40 M) vs `CONTEXT_COMPACTION_THRESHOLD` 100 k, an... (2026-07-23)
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — Added a "View History" button in `SessionArtifacts` that opens a modal timeline of `session_history` rows (step, timestamp, token breakdown). (2026-07-23)
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — Investigated the GitHub-only auth flow end-to-end and created Linear ticket **MNT-148** for adding email/password auth alongside it. (2026-07-23)
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — Revalidated `AGENTS.md` against code/wiki/git-log (4 fixes), deleted redundant `DOCS.md` (391 lines, fully duplicated), added an OpenCode command for automated AGENTS.md maintenance, and registered th... (2026-07-23)
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — Post-merge cleanup for MNT-142 Warp theme plus infra updates: applied review feedback across 7 React components, hardened `bump_project_version` to `log+return None` instead of raising, added Makefile... (2026-07-22)
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — Three sessions covering the React frontend: mapped the component tree and flexbox layout, closed the sidebar–console gap into a single card (border/radius ownership moved to containers, `gap: 0`, `sid... (2026-07-22)
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — Added `FEATURES` dict to `demetra/settings.py` gating `ruff`/`pytest` via `IS_RUFF_ENABLED`/`IS_PYTEST_ENABLED` (both default `False`), and made `demetra/workflows/lint.py:14-17, 31-34` check those fl... (2026-07-22)
- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — MNT-136 hit `Max run attempts reached` after three identical crashes. A review finding containing `[/^\/admin/, ...]` was passed raw to `demetra.services.tui.print_message`, where Rich parsed `[/...]`... (2026-07-21)
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — Sessions with plan-agent questions no longer flip to `Failed` — they now enter an `Awaiting Input` state (stored as `step="awaiting_input"`). (2026-07-21)
- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — Raw ANSI escape sequences (`\x1b[31m` etc.) in logs rendered as garbled text. Fixed by adding stripping via regex `\x1b\[[0-9;]*[a-zA-Z]` at source and in the logging config, covering all handlers. (2026-07-20)
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — Behavior-preserving refactor of `setup_session_logging()` (`demetra/services/utils.py`) after the dedup fix in [[2026-07-15-duplicated-log-messages]]: dropped unused `logger` param (3 call sites), col... (2026-07-16)
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — Two causes for NULL `session_history` tokens: the local DB was missing migration `a2b3c4d5e6f7` (every INSERT failed silently), and on odin prod the migration was applied but all 38 rows still had NUL... (2026-07-16)
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — Code review of the `status`→`step` migration surfaced 4 findings — drifted duplicate step enum, `status`/`step` naming conflation in the API, stale hardcoded return in `upsert_pending_session`, and tw... (2026-07-16)
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — Two listener bugs fixed: (1) `process_merge/rebase_notification` returned `bool` success but `demetra/listener.py` discarded it and always called `mark_notification_read` — failed enqueues were lost. (2026-07-16)
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — Fixed a permanent stall where a run failing before plan save left `step='failed'` + empty `build_plan` → next run skipped planning (`step == 'initial'` gate) and exited forever. (2026-07-16)
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — Two build-workflow logging bugs fixed: (1) `print_message()` lines duplicated in session logs because `setup_session_logging()` compared `Path` to `str` (always `False`), adding a second `FileHandler`... (2026-07-15)
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — Added a fast deploy path: `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, with systemd units and nginx. Auth (GitHub/OpenCode) lives in `.env` via `Environment... (2026-07-07)
- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — Added automatic context-length tracking and compaction for OpenCode sessions. `session_history` records length after each step; when it exceeds `CONTEXT_COMPACTION_THRESHOLD` (default 100_000) the ses... (2026-07-07)
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — Rebuilt the session-log websocket from raw text to typed JSON (`{"type":"log"}` / `{"type":"status"}`) so the React app distinguishes log lines from status transitions. (2026-06-25)
- [Update project version](pages/2026-06-25-update-project-version.md) — Every feature/bugfix workflow now auto-bumps `pyproject.toml`; major bumps are manual. The bump is integrated into the workflow with rollback on failure. Tests added. (2026-06-25)
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — Session artifacts now include a "View Linear Issue" link. A `linear_link` field was added to `sessions` (migration), set on first save when the Linear task is retrieved, returned by the API, and rende... (2026-06-22)
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — PRs now get a generated description instead of an empty body: a Groq-backed service summarises the completed work and the text is passed as the GitHub PR body. Tests added. (2026-06-22)
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — Replaced `patch` DB mocks with fixtures/factories and local service calls with real invocations (third-party calls may stay mocked). (2026-06-15)
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — Project creation was timing out because `run_command` applied the short `SHELL_TIMEOUT_MS` (120s) to OpenCode agent/subprocess calls too, killing long operations like clone and build. (2026-06-10)
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — Added markdown-to-HTML rendering for the build plan in the React app using the `marked` library. A new button in the build-plan modal parses the raw markdown with `marked` and replaces it with the ren... (2026-06-09)
- [Project environment](pages/2026-06-08-project-environment.md) — Added per-project environment variables that are applied to every subprocess the supervisor spawns. (2026-06-08)

## By topic

_Topic clusters maintained by the Consistency Agent; topics with the most pages first._

### React frontend / UI (17 pages)

- [CH-12: Session list order and live status](pages/2026-11-12-ch-12-session-list-order.md) — 2026-11-12
- [MNT-309: Chat Template](pages/2026-11-10-mnt-309-chat-template.md) — 2026-11-10
- [CH-6: Markdown renderer](pages/2026-11-06-ch-6-markdown-renderer.md) — 2026-11-06
- [CH-5: Delete chat button](pages/2026-11-06-ch-5-delete-chat-button.md) — 2026-11-06
- [Chat session list and rerun semantics](pages/2026-11-04-chat-session-list-and-rerun.md) — 2026-11-04
- [CH-2: Single (unified) session view](pages/2026-11-03-ch-2-single-unified-session-view.md) — 2026-11-03
- [Session state flow: completed chain, feedback loops, research chain](pages/2026-10-12-session-state-flow-feedback-loops.md) — 2026-10-12
- [MNT-244: Session state animation](pages/2026-10-12-session-state-animation.md) — 2026-10-12
- [MNT-225: Add copy button](pages/2026-09-27-mnt-225-add-copy-button.md) — 2026-09-27
- [MNT-219: Session log autoscroll](pages/2026-09-24-mnt-219-session-log-autoscroll.md) — 2026-09-24
- [MNT-204: Research result modal](pages/2026-09-14-research-plan-artifact.md) — 2026-09-14
- [MNT-193 — Mobile template for the React frontend](pages/2026-09-02-mobile-template-react-frontend.md) — 2026-09-02
- [Loader replacement and Style Guide page](pages/2026-08-25-loader-styleguide.md) — 2026-08-25
- [Favicon Set for the React App](pages/2026-08-03-favicon-set-and-react-html.md) — 2026-08-03
- [Warp Theme Review Fixes, Infrastructure Updates, and Green Accent Palette](pages/2026-07-22-warp-theme-review-fixes-and-ops.md) — 2026-07-22
- [React Frontend Layout, Template Updates, and Warp Theme CSS Refinements](pages/2026-07-22-react-frontend-template-warp.md) — 2026-07-22
- [Markdown renderer](pages/2026-06-09-markdown-renderer.md) — 2026-06-09

### MCP & wiki tooling (13 pages)

- [Fix the MCP database tools — missing env and broken SQL](pages/2026-10-25-mcp-db-tools-env-sql.md) — 2026-10-25
- [Replace the wiki MCP tool with WI and refactor demetra/tools](pages/2026-10-15-replace-wiki-mcp-tool-with-wi.md) — 2026-10-15
- [BM25 ranking for the wiki and docstring MCP tools](pages/2026-10-09-bm25-search-for-mcp-tools.md) — 2026-10-09
- [LLM-authored wiki pages and normalized frontmatter](pages/2026-10-08-llm-authored-wiki-pages.md) — 2026-10-08
- [MNT-171: Docstring MCP search](pages/2026-09-08-docstring-mcp-search.md) — 2026-09-08
- [Fix wiki index lock not process-safe](pages/2026-08-28-fix-index-lock-concurrency.md) — 2026-08-28
- [Wiki pages not generated — move wiki step before commit](pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) — 2026-08-25
- [Rename wiki budget_exceeded to should_use_llm](pages/2026-08-19-wiki-should-use-llm-rename.md) — 2026-08-19
- [Wiki edge-case fixes and slow-test optimization](pages/2026-08-09-wiki-fixes-and-test-optimization.md) — 2026-08-09
- [Split wiki service into a subpackage](pages/2026-08-07-split-wiki-service-into-subpackage.md) — 2026-08-07
- [MNT-147 Wiki processes PR #70 — branch check and CI failure root cause](pages/2026-08-07-mnt-147-wiki-processes-pr70-review.md) — 2026-08-07
- [Wiki MCP Tools — Search, Read, and List Pages](pages/2026-08-03-wiki-mcp-tools.md) — 2026-08-03
- [Fix MCP Server for the mcp 2.0 API](pages/2026-08-03-fix-mcp-server-2.0-api.md) — 2026-08-03
- [CH-12: Session list order](pages/2026-11-12-ch-12-session-list-order.md) — 2026-11-12

### Session history & token accounting (13 pages)

- [MNT-260: Session calls to openrouter](pages/2026-10-27-mnt-260-openrouter-call-history.md) — 2026-10-27
- [Session history — one row per agent invocation](pages/2026-10-25-session-history-per-invocation-rows.md) — 2026-10-25
- [Session history — cached bundle and MCP tool usage](pages/2026-10-25-session-history-mcp-tool-usage.md) — 2026-10-25
- [Session history — session cost total and failure reasons](pages/2026-10-25-session-history-cost-and-failure-reasons.md) — 2026-10-25
- [MNT-258: Tool usage stats](pages/2026-10-25-mnt-258-tool-usage-stats.md) — 2026-10-25
- [MNT-251 — Rebuild agent session attribution and token accounting for opencode v2](pages/2026-10-16-mnt-251-session-attribution-accounting.md) — 2026-10-16
- [MNT-245: Empty session history](pages/2026-10-16-mnt-245-empty-session-history.md) — 2026-10-16
- [MNT-228: Intermediate history states](pages/2026-09-30-mnt-228-intermediate-history-states.md) — 2026-09-30
- [OpenCode Reasoning Token History Is Zero](pages/2026-09-08-opencode-reasoning-token-zero.md) — 2026-09-08
- [MNT-181: Total tokens counter](pages/2026-08-25-mnt-181-total-tokens-counter.md) — 2026-08-25
- [Session History & Token Consumption Audit (Revalidated)](pages/2026-07-23-session-tokens-audit-revalidation.md) — 2026-07-23
- [Session History Modal](pages/2026-07-23-session-history-modal.md) — 2026-07-23
- [Session history tokens always NULL — pipe truncation in opencode export](pages/2026-07-16-session-history-tokens-null.md) — 2026-07-16

### Workflow orchestration & agents (11 pages)

- [Durable review-round budget in sessions.review_attempts](pages/2026-11-10-durable-review-attempts-budget.md) — 2026-11-10
- [MNT-277: Do not remove git worktree for sessions](pages/2026-11-06-mnt-277-do-not-remove-git-worktree-for-chat-sessions.md) — 2026-11-06
- [MNT-232: Update research flow](pages/2026-10-05-mnt-232-update-research-flow.md) — 2026-10-05
- [MNT-203: Create related ticket for research](pages/2026-09-11-mnt-203-create-related-ticket-for-research.md) — 2026-09-11
- [MNT-200: Update research loop](pages/2026-09-10-mnt-200-update-research-loop.md) — 2026-09-10
- [MNT-177 research loop — research agent, workflow and settings](pages/2026-09-01-mnt-177-research-loop.md) — 2026-09-01
- [Workflow proceeds to review after ticket moved to Awaiting Input](pages/2026-08-28-awaiting-input-workflow-continues-to-review.md) — 2026-08-28
- [Guard empty plan agent output](pages/2026-08-24-guard-empty-plan-output.md) — 2026-08-24
- [Split auth/linear services into subpackages + review-failure handling](pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md) — 2026-08-19
- [Post-build validation — plan-coverage validate-agent between build and review](pages/2026-08-05-post-build-validation.md) — 2026-08-05
- [Fix empty build plan infinite loop](pages/2026-07-16-fix-empty-build-plan-loop.md) — 2026-07-16

### Deploy & infrastructure (9 pages)

- [Forward LangSmith env vars from host to containers](pages/2026-09-28-compose-langsmith-host-env.md) — 2026-09-28
- [Bake opencode agents and skills into the Docker image](pages/2026-09-18-dockerfile-opencode-agents-skills.md) — 2026-09-18
- [gh config.yml permission denied in containers — un-gated entrypoint ownership repair](pages/2026-08-24-gh-config-dir-permission-entrypoint.md) — 2026-08-24
- [Code review — gh CLI auth mount and entrypoint prune for compose](pages/2026-08-20-review-gh-auth-mount-changes.md) — 2026-08-20
- [Worker opencode EACCES on home volume — entrypoint ownership fix](pages/2026-08-19-worker-opencode-home-permissions.md) — 2026-08-19
- [Docker Compose shared-anchor refactor](pages/2026-08-18-compose-anchors-refactor.md) — 2026-08-18
- [Docker setup review — Dockerfile + docker-compose.yaml on mnt-164](pages/2026-08-17-docker-setup-review.md) — 2026-08-17
- [Docker Compose deploy](pages/2026-08-10-docker-compose-deploy.md) — 2026-08-10
- [Project deploy script](pages/2026-07-07-project-deploy-script.md) — 2026-07-07

### OpenCode CLI & agent integration (9 pages)

- [MNT-298 research agent ECONNRESET — local opencode server thrash](pages/2026-11-06-mnt-298-research-econnreset-root-cause.md) — 2026-11-06
- [Agent ECONNRESET network errors — root cause](pages/2026-11-06-agent-econnreset-network-investigation.md) — 2026-11-06
- [MNT-276: ECONNRESET retry for agents](pages/2026-11-03-mnt-276-econnreset-retry-for-agents.md) — 2026-11-03
- [OpenCode v2 migration — CLI ground truth, the compaction no-op, and the corrected MNT-251 plan](pages/2026-10-16-opencode-v2-session-token-accounting.md) — 2026-10-16
- [MNT-234: Isolate session context](pages/2026-10-16-mnt-234-isolate-session-context.md) — 2026-10-16
- [OpenCode agent system prompts — permission hardening, injection guards, and merge/rebase semantics](pages/2026-09-14-opencode-agent-prompts-hardening.md) — 2026-09-14
- [Build agent UnknownError — stale opencode session bound to deleted worktree](pages/2026-08-19-build-agent-stale-session-deleted-worktree.md) — 2026-08-19
- [Build agent server error — root cause and Awaiting Input handler](pages/2026-08-19-build-agent-server-error-handler.md) — 2026-08-19
- [Plan loop resolve agent received truncated context](pages/2026-08-04-fix-resolve-agent-truncated-context.md) — 2026-08-04

### Environment, settings & subprocess (8 pages)

- [Review agent models bypass the environment layers](pages/2026-10-12-review-models-env-resolution.md) — 2026-10-12
- [Unify subprocess env on SessionEnvironment](pages/2026-10-06-unify-subprocess-env-on-session-environment.md) — 2026-10-06
- [MNT-205 — Revise merged environment: context.environment resolver](pages/2026-09-16-mnt-205-revise-merged-environment.md) — 2026-09-16
- [MNT-192 Add edit button for env settings](pages/2026-08-31-mnt-192-env-edit-button.md) — 2026-08-31
- [Categorize settings env vars by layer](pages/2026-08-18-categorize-settings-env-vars-by-layer.md) — 2026-08-18
- [Process environment — 3 layers, encryption, UV venv, env file upload](pages/2026-08-10-process-environment-3-layers-encryption-uv-venv.md) — 2026-08-10
- [Fix Project creation timeouts](pages/2026-06-10-fix-project-creation-timeouts.md) — 2026-06-10
- [Project environment](pages/2026-06-08-project-environment.md) — 2026-06-08

### Authentication & API security (7 pages)

- [MNT-188: Waitlist](pages/2026-08-28-mnt-188-waitlist.md) — 2026-08-28
- [Fix allowlist tests after MNT-173 default-on refactor](pages/2026-08-20-fix-allowlist-tests.md) — 2026-08-20
- [Allowlist CodeRabbit Review Fixes and CI Test Fix](pages/2026-08-06-allowlist-review-fixes.md) — 2026-08-06
- [Check API Auth — Dependency Consolidation, Session Ownership, and Credential Hygiene](pages/2026-08-03-check-api-auth-and-credentials.md) — 2026-08-03
- [Password Hashing, Cookie & CORS Hardening, and Dependency Bump](pages/2026-08-03-auth-hardening-and-deps-bump.md) — 2026-08-03
- [Plain Password Auth Implementation and Review Follow-ups](pages/2026-07-24-plain-auth-review-followups.md) — 2026-07-24
- [Linear Ticket for Email/Password Authentication](pages/2026-07-23-linear-ticket-email-password-auth.md) — 2026-07-23

### Linear & GitHub integrations (8 pages)

- [Unified Task model with Linear and Chat subtypes](pages/2026-11-11-mnt-312-unified-task-model.md) — 2026-11-11
- [CH-10: PR description for Chat sessions](pages/2026-11-10-ch-10-pr-description-for-chat-sessions.md) — 2026-11-11
- [Listener fails to pick up comments — asyncio readline 64KB limit on gh notifications](pages/2026-09-14-listener-readline-limit-crash.md) — 2026-09-14
- [Ticket status isn't changed when watcher picks it up](pages/2026-08-28-mnt-191-ticket-status-not-changed.md) — 2026-08-28
- [PR creation failure moves ticket to Awaiting Input](pages/2026-08-05-pr-creation-failure-handler.md) — 2026-08-05
- [Fix notification mark-as-read and add infinite-loop protection](pages/2026-07-16-fix-notification-mark-read.md) — 2026-07-16
- [Linear link artifact](pages/2026-06-22-linear-link-artifact.md) — 2026-06-22
- [GitHub PR description](pages/2026-06-22-github-pr-description.md) — 2026-06-22

### Docs, release & versioning (4 pages)

- [MNT-176: Bump version error fix](pages/2026-08-21-mnt-176-bump-version-error.md) — 2026-08-21
- [AGENTS.md Revalidation and Wiki Consistency Audit](pages/2026-08-03-agents-md-and-wiki-consistency.md) — 2026-08-03
- [AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command](pages/2026-07-23-agents-md-revalidation-and-docs-removal.md) — 2026-07-23
- [Update project version](pages/2026-06-25-update-project-version.md) — 2026-06-25

### Code review & quality (3 pages)

- [Review findings cleanup — v1.16.7..HEAD two-axis review](pages/2026-09-02-review-findings-cleanup.md) — 2026-09-02
- [Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int](pages/2026-08-09-apply-pr75-coderabbit-findings.md) — 2026-08-09
- [Apply code-review findings — auth, transactions, validate, wiki](pages/2026-08-09-apply-code-review-findings.md) — 2026-08-09

### LLM & prompts (3 pages)

- [MNT-308: Lint and test erorrs](pages/2026-11-10-mnt-308-lint-error-extraction.md) — 2026-11-10
- [MNT-177 workflow blocked — OpenRouter 403 age attestation + plan agent truncation](pages/2026-08-28-mnt-177-workflow-blocked-openrouter-403.md) — 2026-08-28
- [Migrate LLM summarization from Groq to OpenRouter](pages/2026-08-18-migrate-llm-groq-to-openrouter.md) — 2026-08-18

### Logging (3 pages)

- [Resolve ANSI Color Escape Codes in Logs](pages/2026-07-20-resolve-ansi-color-escape-codes-in-logs.md) — 2026-07-20
- [Simplify setup_session_logging](pages/2026-07-16-simplify-session-logging-setup.md) — 2026-07-16
- [Duplicated log messages and missing build agent logs](pages/2026-07-15-duplicated-log-messages.md) — 2026-07-15

### Sessions, status & state flow (4 pages)

- [Unified Task model with Linear and Chat subtypes](pages/2026-11-11-mnt-312-unified-task-model.md) — 2026-11-11
- [Awaiting Input status for session](pages/2026-07-21-awaiting-input-status-for-session.md) — 2026-07-21
- [Fix code-review findings on step/status refactor](pages/2026-07-16-fix-step-status-review-findings.md) — 2026-07-16
- [Websocket to track session statuses](pages/2026-06-25-websocket-to-track-session-statuses.md) — 2026-06-25

### Testing & tooling (3 pages)

- [Test DB isolation and console-only logging](pages/2026-08-18-test-db-isolation-logging.md) — 2026-08-18
- [Add tests for existing feature-flag changes](pages/2026-07-22-feature-flag-settings-and-tests.md) — 2026-07-22
- [Remove patches from tests where possible](pages/2026-06-15-remove-patches-from-tests.md) — 2026-06-15

### Context, tokens & compaction (1 page)

- [Add context compaction](pages/2026-07-07-add-context-compaction.md) — 2026-07-07

### TUI & CLI (1 page)

- [Rich MarkupError kills workflow subprocess and run_attempts counter overcounts](pages/2026-07-21-rich-markuperror-and-run-attempts.md) — 2026-07-21