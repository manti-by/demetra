# AGENTS.md

## Project Overview

Demetra is an autonomous coding platform that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

## Project Structure

- `main.py`: CLI entry point and supervisor orchestration
- `demetra/settings.py`: Core configuration and environment variables
- `demetra/library/`: Pure data layer (dataclasses, TypedDicts, exceptions, tables, constants, env validation in `env.py`, `header.py` banner helpers)
- `demetra/services/`: External system and cross-cutting integrations (`agents/`, `auth/`, `chat/`, `daemons/`, `linear/`, `llm/`, `persistence/`, `quality/`, `runtime/`, `vcs/`, `wiki/` plus `utils.py` shared helpers: waitlist-join audit, auth rate limiter)
- `demetra/queries/`: GraphQL queries
- `demetra/workflows/`: Workflow orchestration steps (`plan`, `research`, `resolve`, `build`, `validate`, `review`, `lint`, `cleanup`, `merge`/`rebase`, `review_fixes`, `setup`, `failure`, `postprocess`, `notifications`, etc.)
- `demetra/api/`: FastAPI REST endpoints (`auth`, `chats`, `chat_templates`, `github`, `projects`, `sessions`, `users`, `watcher`, `webhooks` plus `responses.py` shared helpers: `waitlisted_response`, `delete_cookie_header`, `client_host`)
- `demetra/tools/`: MCP tool definitions (`database`, `docstrings`, `logs` plus shared `config`/`corpus`/`models`/`search`/`registry`/`utils` helpers)
- `demetra/prompts/`: LLM prompt templates (`research_agent`, `validate_agent`, `resolve_questions`, `merge_agent`, `rebase_agent`, `analyze_ticket`, etc.)
- `demetra/templates/`: Linear failure-comment message templates (`agent_network_failed`, `build_failed`, `pr_creation_failed`, `review_failed`, `wiki_failed`) plus `chat/` — Markdown chat templates (`feature_template.md`, `research_template.md`) served by `demetra/api/chat_templates.py`
- `demetra/app.py`: FastAPI application
- `demetra/mcp_server.py`: MCP server
- `demetra/watcher.py` / `demetra/listener.py` / `demetra/deployer.py` / `demetra/worker.py`: Thin entrypoints (watcher/listener/deployer logic lives in `demetra/services/daemons/`; watcher = Linear TODO poller, listener = GitHub notifications, deployer = origin/master poller that deploys once the commit's CI checks passed and the RQ queue drained; `worker.py` is a self-contained RQ worker — the queue's `default_timeout` is `SUBPROCESS_TIMEOUT` (`demetra/services/persistence/queue.py:16`), so raising `SUBPROCESS_TIMEOUT` past the old hardcoded 3600s no longer kills workflow jobs mid-run). `demetra/deploy_lock.py` wraps the `make deploy` recipe (`python -m demetra.deploy_lock -- ...`, Makefile:27) in the same Redis lock the deploy daemon takes (`demetra/services/daemons/deploy_lock.py`), so a manual deploy cannot overlap the daemon)
- `react/`: React frontend (Vite + TypeScript)
- `migrations/`: Alembic database migrations
- `alembic.ini`: Alembic configuration (drives the migration commands)
- `tests/`: Comprehensive test suite (67 `test_*.py` files, 69 total with `__init__.py`/`conftest.py`)
- `configs/`: Docker entrypoint (`configs/docker-entrypoint.sh`), provider-only OpenCode config derivation (`configs/derive-opencode-config.py`) and nginx config (`configs/nginx.conf`, `configs/proxy.params`) — `bootstrap.sh` and the systemd units (`configs/services/*.service`) were removed in `f5904d5` (2026-09-11) when `make deploy` moved to Docker; a standalone `configs/deployer.service` was added in `583d19c` (2026-11-24) for running the deployer under systemd on the host, while the Docker path uses the compose `deployer` service
- `wiki/audits/`: Dated audit directories (workflow audits, `2026-11-05-security-audit/` with numbered security findings) plus `workflow-state-machine.html` interactive Mermaid diagram (static asset)
- `Dockerfile`, `docker-compose.yaml`, `.dockerignore`: containerized deploy (api/worker/watcher/listener/rq-dashboard + one-shot React build; see `make deploy` / `make docker-up`). The image bakes the `opencode` and `wi` binaries onto `PATH` — both are version-pinned build args (`OPENCODE_VERSION`, `WI_VERSION`), and the final stage asserts `opencode --version` matches `OPENCODE_VERSION`, so a stale cached `COPY --from=builder` fails the build instead of shipping an old binary; `wi` is the external MCP server wired into `opencode.json`, so agents can launch it in-container. The host provider-credential file is mounted read-only as `~/.config/opencode/providers.json`; `configs/derive-opencode-config.py` derives the global `opencode.json` from it at container start, keeping `$schema` + `provider` only so host MCP/agent sections cannot shadow the project config. The Rust toolchain (`/usr/local/cargo`, `/usr/local/rustup` from `rust:1-slim`), the C toolchain (`gcc g++ make libc6-dev pkg-config`) and `bun` are required runtime dependencies even though Demetra itself never calls them: agents build and test the target projects Demetra manages (Rust, native-extension and JS projects) inside the container, so do not drop them to shrink the image. The runtime image carries no dev dependencies or `tests/`; `make docker-test` (`docker-compose.test.yaml`) bind-mounts the repo, installs the dev group into `/opt/venv` of a throwaway container and runs migrations + `pytest` against a disposable Postgres
- `.github/workflows/`: GitHub Actions CI (`checks.yml`)
- `.opencode/`: OpenCode agent definitions in `agents/` (8 `*-agent.md` files: `build`, `merge`, `plan`, `rebase`, `research`, `resolve`, `review`, `validate` with `description`/`permission` frontmatter; npm manifest pins `@opencode-ai/plugin`). `.opencode/skills/` is gitignored: skills resolve as installed skills (`wiki-sync`, `wiki-consistency`, `wiki-dedup`, `wiki-archive`, `wiki-agents-file`, `code-review`, plus the release/fix skills)
- `opencode.json`: OpenCode agent toolchain configuration (MCP servers Demetra/WI/Linear; `plugins` list is empty — the `@langchain/langsmith-opencode` plugin was removed in `67d106c`, tracing now flows via env vars, see LangSmith below). The Linear MCP server is authenticated with a static `Authorization: Bearer {env:LINEAR_API_KEY}` header and `oauth: false`, fed from the environment layers; the Demetra MCP command no longer passes a cwd-relative `--env-file`
- `wiki/`: Persistent session knowledge base (pages, `INDEX.md` catalog + `By topic` clusters, `QUESTIONS.md` open discrepancies, `postmortems/` blameless incident postmortems per `postmortems/README.md`, 4 page types per `TEMPLATE.md` — see `wiki/README.md`; `.sessions.json` maps session ids to pages, machine-maintained; `wiki/archive/` holds retired pages preserved for provenance standard markdown `/archive/...` links)

## Wiki

The `wiki/` directory is a persistent, compounding knowledge base: one Markdown page per session (debug chase, investigation, code review, or set of changes), cross-linked into a knowledge graph. `wiki/pages/` + `wiki/archive/` are an Open Knowledge Format bundle: each page carries `generated: {by: demetra, at: <ISO 8601 UTC>}` (replacing `date`), a one-sentence `description`, and `status: stable|draft|deprecated` (`deprecated` for archived pages). Cross-links use standard markdown links `[stem](/pages/stem.md)` or `[stem](/archive/stem.md)`, not `[[wikilinks]]`. Conventions and the page template: [wiki/README.md](wiki/README.md); the catalog of all pages: [wiki/INDEX.md](wiki/INDEX.md) (`## Pages` newest-first + `## By topic` clusters auto-maintained by `wiki-consistency`); open discrepancies tracked in [wiki/QUESTIONS.md](wiki/QUESTIONS.md). The one-time validator/migrator runs as `uv run python -m demetra.services.wiki.okf --dry-run`.

- Before planning or building, skim `wiki/INDEX.md` for prior sessions on the same subsystem.
- For questions about past incidents, design decisions, or prior investigations, search the wiki first via the WI MCP tools (`wiki_search`, browse the catalog with `wiki_list_pages`, fetch a full page with `wiki_get_page`).
- After a session, record it as a page using `wiki/TEMPLATE.md` and keep the index and cross-links current (see the installed `wiki-sync` skill and `wiki-consistency`/`wiki-dedup`/`wiki-archive`/`wiki-agents-file` skills).

## Git Workflow

This project adheres strictly to the Git Flow branching model. AI agents must follow these guidelines:

### Main Branch:

- The `master` branch always contains production-ready, stable code.
- Never commit directly to `master`.
- Do not use `git push --force` on the `master` branch.
- Do not merge branches into `master` without explicit approval.

### Feature Branches:

- Create feature branches using the naming convention `<agent-name>/feature/<issue-id>-<descriptive-name>` (e.g., `opencode/feature/DEMETRA-10-add-user-authentication`).
- Use the [Conventional Commits](https://www.conventionalcommits.org) specification for commit messages (e.g., `feat:`, `fix:`, `docs:`).
- Ensure all local tests pass before committing.
- Use `git push --force-with-lease` if needed on your feature branch, but never on `master`.

### Pull Requests (PRs):

- Open a Pull Request for every completed feature branch.
- PRs must be reviewed and pass all CI checks before merging.
- The PR title should follow the Conventional Commits specification.

## Linear Workflow

- When starting implementation of any issue from `TODO`, move it to `In Progress` column.
- When feature is completed and PR is created, move it to `In Review` column.
- After approval, merge the feature branch into `master` and move the issue to `Done` column.
- If the feature branch is not merged into `master`, move it back to `In Progress` column.
- If the feature branch is closed without merging, move it to `Closed` column.

## Development Commands

### Package Management

```bash
# Install dependencies (including dev extras)
uv sync --all-extras --dev

# Upgrade dependencies and pre-commit hooks (Makefile:59-61)
make update                          # uu + uv sync --all-extras --dev + pre-commit autoupdate
```

`uu` is an external CLI, not a project dev dependency; the old `uv-bump` dev dependency was removed in `9625097`.

### Running Modules

From the project root, after creating a virtualenv and installing dependencies:

```bash
uv run main.py --project-name <project_name>
```

### Containerized Deploy

`make deploy` is the deploy path and runs the full app layer (Postgres, Redis, API, workers, watcher, listener, deployer, RQ dashboard and a one-shot React build) on top of the `mantiby/demetra` image. The old systemd path (`configs/bootstrap.sh`, `configs/services/*.service`, `systemctl restart demetra-*`) was removed in `f5904d5` (2026-09-11).

Prerequisites: Docker Compose v2 (the `docker-up` target passes `--scale worker=4` so 4 workers run — the compose file declares `worker.deploy.replicas: 4` as a default at `docker-compose.yaml:125`; the `deploy` target also uses `--scale worker=4` at `Makefile:34`, and the deploy daemon's `build_deploy_steps` mirrors it); the `mantiby/demetra:latest` image (built from the local Dockerfile by `make docker-build`), and `docker-build` needs Docker BuildKit.

```bash
cp .env.docker.example .env.docker   # then fill in real values
make check-compose                   # validate docker-compose.yaml (docker compose --env-file .env.docker config -q)
make deploy                          # git pull + build + pull infra + migrate/react one-shots + up long-running (scale 4) + nginx reload
make deploy-ui                       # git pull + react one-shot build + nginx reload (frontend only)
# pure-Docker path (no git pull / nginx reload):
make docker-build && make docker-up  # build image + up with 4 workers (Makefile:119-129); `postgres`/`redis`/`oven/bun` pulled automatically
```

`make deploy-ui` ships frontend-only changes: it pulls, rebuilds the React bundle through the one-shot `react-build` service and reloads nginx, leaving the image, the migrations and the running containers untouched — a UI change goes live without restarting the API or interrupting the running workflows. It takes the same Redis deploy lock as `make deploy` (`demetra/deploy_lock.py`), so it cannot overlap the deploy daemon, which rebuilds the same bundle.

## Language & Environment

- Python >=3.14.10, <3.15.0 (see `pyproject.toml:6`; the Dockerfile builds on `python:3.14-slim`)
- Follow PEP 8 style guidelines, with Ruff enforcing style and linting (120 char line length)
- Use type hints for public functions and complex code paths
- Use only f-strings for string formatting (never use `.format()` or `%` formatting; sole exceptions: prompt-template substitution in `demetra/services/llm/prompt.py` and message-template substitution in `demetra/services/runtime/template.py`)
- Use list/dict/set comprehensions instead of `map`/`filter` where it improves readability
- Prefer `pathlib.Path` over `os.path` for filesystem paths
- Follow PEP 257 for docstrings where docstrings are used
- Use only named arguments instead of positional arguments in function and method calls

## Code Style & Tooling

Configured in `pyproject.toml`:

- **Ruff** for linting and import management (`[tool.ruff]`, `[tool.ruff.lint]`)
- **Bandit** for basic security checks (`[tool.bandit]`)
- **pre-commit** is used to run the tools before commits
- **ty** for type checking

Run manually:

```bash
uv run pre-commit run --all-files
uv run ruff check .
uv run ty check
uv run bandit -c pyproject.toml .
```

## Code Conventions

**Naming** (ruff N enforces most):
- Modules: `snake_case.py`; tests mirror at `tests/test_<module>.py`
- Classes: `PascalCase`; dataclasses in `library/models.py`, TypedDicts in `library/types.py`, env validation in `library/env.py`
- Functions: `snake_case`; module-level private helpers use a leading `_` (e.g. `demetra/tools/database.py`, `demetra/tools/docstrings.py`); external-CLI wrappers prefix the system name (`opencode_*`, `git_*`, `cursor_*`)
- Constants: `UPPER_SNAKE_CASE`; env-driven ones live in `demetra/settings.py`

**Architecture** (strict layering, no skipping):
- `demetra/library/` — pure: dataclasses, TypedDicts, exceptions, tables. No I/O.
- `demetra/services/<system>/` — one external system or cross-cutting area per subpackage (`agents/`, `auth/`, `chat/`, `daemons/`, `linear/`, `llm/`, `persistence/`, `quality/`, `runtime/`, `vcs/`, `wiki/`); `auth/`, `chat/`, `linear/`, `llm/`, `vcs/`, `wiki/` re-export through a facade `__init__.py`, while `agents/`, `daemons/`, `persistence/`, `quality/`, `runtime/` are plain packages imported by submodule path (e.g. `demetra.services.runtime.tui`). Subprocess wrappers return `tuple[int, str, str]` (`exit_code, stdout, stderr`).
- **Task model** — `demetra/library/models.py` defines the generic `Task` base (`kind: "linear" | "chat"`, `identifier`, `title`, `description`, `priority`, `state`, `url`, `tags`, `project_id`, `user_id`, `messages`) and the generic `Message` base (`task_id`, `parent_id`, `source`, `external_id`, `author_id`, `author_name`, `is_system`, `kind`, `body`). `LinearTask(Task)` / `Chat(Task)` and `LinearComment(Message)` / `ChatMessage(Message)` are the subtypes; the dataclasses are `kw_only=True` so subtypes can add defaulted fields. `Context.task` is the task of a workflow (it was `Context.linear_task`). Persistence: `tasks` (generic identity, `kind` discriminator), `linear_tasks` (Linear subtype), `messages` (unified history), `chats` (chat subtype row: `id` + `task_id`), `sessions` (workflow state, `task_id` FK → `tasks.id`). Linear issues and their comments are mirrored locally by `demetra/services/linear/mirror.py`; the backfill CLI is `main.py --linear-sync [--dry-run]` (`demetra/services/linear/sync.py`).
- `demetra/workflows/<step>.py` — orchestrators; receive `Context`, call services. Entry points typically `run_<step>_*` (includes `review_fixes.py` for the `@demetra-ai fix review findings` listener flow and `research.py` for the `Research` label loop — creates related Linear ticket, persists `research_report`, uses `research` → `researched` steps (source ticket moved to In Review; step stays `research` if the Linear move fails)). Workflows read env via `Context.environment` (`SessionEnvironment` in `demetra/library/models.py`: project → user-shared → settings fallback, `EnvironmentConfigError` on missing key; see `wiki/pages/2026-09-16-mnt-205-revise-merged-environment.md`).
- `demetra/api/<resource>.py` — FastAPI `router = APIRouter(...)`; thin, delegates to services.
- `demetra/tools/<system>.py` — MCP tool modules (`database.py`, `docstrings.py`, `logs.py`) exposing `async def list_tools()` and `async def call_tool(name, arguments)`; dispatchers return a shared `ToolResult` (`demetra/tools/models.py`) carrying `content` + `is_error`. Shared helpers: `demetra/tools/config.py` (filesystem roots), `demetra/tools/models.py` (dataclasses), `demetra/tools/corpus.py` (frozen `Corpus`/`Ranked` snapshot + `CorpusCache` mtime/size cache, replacing per-module globals), `demetra/tools/search.py` (BM25F tokenization and scoring), `demetra/tools/utils.py` (`resolve_limit`). `demetra/tools/registry.py` aggregates them via a `MODULES`/`HANDLERS` table, re-exported through `demetra/tools/__init__.py`; `mcp_server.py` calls the package-level `list_tools` / `call_tool` and closes the DB pool on shutdown. The project wiki is no longer an MCP tool — it is served by the external WI MCP server (see `opencode.json`).

**Do NOT use**: `print()` (use `print_message` from `demetra.services.runtime.tui`; sole exception: `mcp_server.py` startup banner to stderr), PEP 585 typing (`Tuple[X]/Optional[X]/List[X]/Dict[X]` — use PEP 604 `X | None` / `list[X]`), mutable default arguments (use `field(default_factory=...)`), inline comments and emojis in code, bare `except Exception:` (catch specific `OSError`/`RuntimeError` instead; the accepted uses are MCP `call_tool` dispatchers that `logger.exception`, workflow cleanup paths carrying `# noqa: BLE001`, daemon poll-loop guards (`demetra/watcher.py:40`, `demetra/listener.py:85`, `demetra/deployer.py`), LLM-call boundary guards that `logger.exception` and raise a typed error (`demetra/services/llm/openrouter.py`), and best-effort copy/cleanup guards that `logger.exception` (`demetra/services/auth/copy.py`, `demetra/services/runtime/project.py:312,323`)) and `# noqa` suppressions — check `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.per-file-ignores]`, `[tool.bandit]`, `[tool.ty.src]`) for the canonical list of allowed ignores/exclusions for `ruff`, `ty` and `bandit`; do not add new suppressions without updating config.

**Imports**: Always place imports at the top of the file (global scope). Local imports inside functions are permitted only in rare cases where they are necessary to resolve circular import dependencies.

**Feature flags**: `demetra/settings.py` defines `FEATURES` (`is_ruff_enabled`, `is_pytest_enabled` from `IS_RUFF_ENABLED` / `IS_PYTEST_ENABLED`, both default `False` — `demetra/workflows/lint.py` only runs `ruff`/`pytest` when package installed *and* flag `True`; plus `is_worktree_cleanup_enabled` from `WORKTREE_CLEANUP`, default `False` — when enabled a session drops its worktree and branch, pulls master and creates a fresh worktree at start, and removes the worktree at end; when disabled an existing worktree is reused and kept), `SEARCH` (docstring weights and limits; stop words live as `SEARCH_STOP_WORDS` in `demetra/library/constants.py`, consumed by `demetra/tools/search.py`), `WIKI` budgets (`WIKI_DIFF_HUNK_CAP` (max lines of unified diff passed to the page author as its only source of real code) /`_BUILD_PLAN_CAP`, `WIKI_REVALIDATION_ENABLED`; wiki pages are always LLM-authored via `compose_wiki_page`, there is no budget gate — a body missing any `WIKI_REQUIRED_SECTIONS` heading in `demetra/library/constants.py` raises `WikiError` and no page is written), `MAX_ATTEMPTS` (per-step retry budgets keyed by workflow — `run`/`plan`/`build`/`review`/`merge`/`rebase`/`listener`/`research`, each read from its `MAX_*_ATTEMPTS` env var; the review budget is persisted durably in `sessions.review_attempts` and survives worker restarts — commit `8749154`, wiki `durable-review-attempts-budget`), the `DEPLOY` config for the deploy daemon (`DEPLOYER_POLL_INTERVAL` 60, `DEPLOY_MIN_INTERVAL` 300, `DEPLOY_DRAIN_TIMEOUT` 3600 / `DEPLOY_STEP_TIMEOUT` 15000, `DEPLOY_HOST_CHECKOUT` default `/home/manti/www/demetra`, `DEPLOY_REPOSITORY`, `DEPLOY_STATE_PATH` default `/var/lib/demetra/deployer-state.json`, `DEPLOY_NGINX_RELOAD_COMMAND`, and the `compose_services` list that deliberately omits `deployer`), and the agent network-retry pair (`MAX_AGENT_NETWORK_ATTEMPTS` default 5, `AGENT_NETWORK_BACKOFF_BASE` default 1.0 — exponential-backoff retries of transient opencode agent network errors such as `ECONNRESET`/`ETIMEDOUT`, set up by MNT-276). Lint/tests are opt-in.

## Testing Guidelines

- Use `pytest` for tests
- Tests live in `tests/` directory
- Run with `make test` or `uv run pytest tests/`
- Group test cases in classes named `Test<Feature>` (e.g. `TestWaitlistCliList`); do not use module-level `def test_*` functions for new tests (legacy module-level tests remain in `tests/test_allowlist_cli.py` and `tests/test_migrations.py`)
- When testing OpenCode invocations (validating output format, extracting token usage, checking `--help`, smoke runs, etc.), use free models whenever possible instead of paid ones — pick a free-tier model for throwaway verification runs and reserve paid models for the real pipeline

## Database Migrations

When creating Alembic migrations:

- Use descriptive names in snake_case (e.g., `add_users_table`, `drop_sessions_column`, `create_oauth_tokens_index`)
- Prefix with operation type: `add_`, `create_`, `drop_`, `alter_`, `remove_`, `rename_`
- Include the table name and what changed
- Example: `uv run alembic revision --autogenerate -m "add_user_keys_column"`

## Environment & Configuration

Environment is controlled primarily via `demetra/settings.py` and `.env`. Agent subprocesses inherit `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_NAME` (project → user-shared → system) but not a system `DB_PASSWORD`: the Demetra MCP server reads the encrypted project/user `DB_PASSWORD` entry and exits at startup when it is missing.

## Dependencies

Declared in `pyproject.toml` (core under `dependencies`, dev tooling under `[dependency-groups] dev`) and locked in `uv.lock`.

## External Dependencies

Demetra coordinates the following external tools:

- **OpenCode**: AI coding assistant for planning and building features; agent runs use the `--standalone` flag when the CLI advertises it — support is probed from `run --help` and cached per CLI path (`opencode_supports_standalone`, `demetra/services/agents/opencode.py:646-678`)
- **Cursor**: AI-powered code review tool
- **CodeRabbit**: Alternative AI code review tool
- **Linear**: Issue tracking via GraphQL API; issues and their comments are mirrored into the local `tasks`/`messages` tables (`demetra/services/linear/mirror.py`), backfilled with `main.py --linear-sync`. The Linear MCP server (`https://mcp.linear.app/mcp`) authenticates with `LINEAR_API_KEY` as a static Bearer header resolved project → user-shared → system (`SessionEnvironment.system_env`)
- **GitHub**: PR creation and notification-driven merge/rebase/`fix review findings` triggers (`demetra/listener.py` → `demetra/services/daemons/listener.py` → `demetra/workflows/review_fixes.py`)
- **OpenRouter**: LLM API for plan extraction, lint/test error extraction (`extract_errors`, MNT-308), review and wiki summarisation, and PR description generation (`demetra/services/llm/openrouter.py`)
- **WI**: project wiki search/read/list via MCP (`opencode.json` `mcp.servers.WI`, `wi` command) — the in-repo `wiki_*` MCP tools were removed in favour of it
- **LangSmith**: tracing via environment variables, not an OpenCode plugin (`plugins: []` since `67d106c`). Tracing is one platform-wide configuration: `docker-compose.yaml` forwards host `LANGSMITH_*` into containers with tracing opt-in (default `false`), and `settings.LANGSMITH` gates tracing on a configured API key (a whitespace-only key counts as missing) and forces in-process tracing off when there is none. `SessionEnvironment.system_env` derives the same flags from that single source — project/user layer overrides are ignored — so all sessions share the configured platform project, `LANGSMITH_PROJECT` (default `Demetra`); the platform API key must be authorized for that project. The shared key itself is kept out of `system_env`: only the agent run that emits traces receives it, via `SessionEnvironment.tracing_env` and `forward_tracing=True` (`demetra/library/models.py:782`, `demetra/services/runtime/subprocess.py:32`, `demetra/settings.py:247`)

## Security Guidelines

- Never commit secrets, passwords, or API tokens
- Configure sensitive values via environment variables
- Run `bandit` periodically or in CI
- Validate any external input before using it in system calls or network operations

## AI Behavior

Response style — concise and minimal: working code without boilerplate or unnecessary explanation, clear naming over comments, no tangential suggestions.
