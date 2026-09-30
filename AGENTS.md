# AGENTS.md

## Project Overview

Demetra is an autonomous coding platform that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

## Project Structure

- `main.py`: CLI entry point and supervisor orchestration
- `demetra/settings.py`: Core configuration and environment variables
- `demetra/library/`: Pure data layer (dataclasses, TypedDicts, exceptions, tables, constants, env validation in `env.py`, `header.py` banner helpers)
- `demetra/services/`: External system and cross-cutting integrations (`agents/`, `auth/`, `daemons/`, `linear/`, `llm/`, `persistence/`, `quality/`, `runtime/`, `vcs/`, `wiki/` plus `utils.py` shared helpers: waitlist-join audit, auth rate limiter)
- `demetra/queries/`: GraphQL queries
- `demetra/workflows/`: Workflow orchestration steps (`plan`, `research`, `resolve`, `build`, `validate`, `review`, `lint`, `cleanup`, `merge`/`rebase`, `review_fixes`, `setup`, `failure`, `postprocess`, etc.)
- `demetra/api/`: FastAPI REST endpoints (`auth`, `github`, `projects`, `sessions`, `users`, `watcher`, `webhooks` plus `responses.py` shared helpers: `waitlisted_response`, `delete_cookie_header`, `client_host`)
- `demetra/tools/`: MCP tool definitions (`database`, `docstrings`, `projects`, `wiki` plus `search`/`result`/`registry` helpers)
- `demetra/prompts/`: LLM prompt templates (`research_agent`, `validate_agent`, `resolve_questions`, `merge_agent`, `rebase_agent`, etc.)
- `demetra/templates/`: Linear failure-comment message templates (`build_failed`, `pr_creation_failed`, `review_failed`, `wiki_failed`)
- `demetra/app.py`: FastAPI application
- `demetra/mcp_server.py`: MCP server
- `demetra/watcher.py` / `demetra/listener.py` / `demetra/worker.py`: Thin entrypoints (watcher/listener logic lives in `demetra/services/daemons/`; watcher = Linear TODO poller, listener = GitHub notifications; `worker.py` is a self-contained RQ worker)
- `react/`: React frontend (Vite + TypeScript)
- `migrations/`: Alembic database migrations
- `alembic.ini`: Alembic configuration (drives the migration commands)
- `tests/`: Comprehensive test suite (52 `test_*.py` files, 54 total with `__init__.py`/`conftest.py`)
- `configs/`: Docker entrypoint (`configs/docker-entrypoint.sh`) and nginx config (`configs/nginx.conf`, `configs/proxy.params`) — `bootstrap.sh` and the systemd units (`configs/services/*.service`) were removed in `f5904d5` (2026-09-11) when `make deploy` moved to Docker
- `wiki/audits/`: Workflow audit notes plus `workflow-state-machine.html` interactive Mermaid diagram (static asset)
- `Dockerfile`, `docker-compose.yaml`, `.dockerignore`: containerized deploy (api/worker/watcher/listener/rq-dashboard + one-shot React build; see `make deploy` / `make docker-up`)
- `.github/workflows/`: GitHub Actions CI (`checks.yml`)
- `.opencode/`: OpenCode agent (8 agents: `build`, `merge`, `plan`, `rebase`, `research`, `resolve`, `review`, `validate` with `description`/`permission` frontmatter) and skill definitions (`wiki-sync` — the other vendored skills were removed in `94fefa7`, 2026-09-23; `wiki-consistency`/`wiki-dedup`/`wiki-archive`/`wiki-agents-file` and the release skills now resolve as installed skills)
- `opencode.json`: OpenCode agent toolchain configuration (MCP servers including Playwright, plugins including LangSmith)
- `.claude/agents/`: Claude Code subagent definitions, one `.md` per OpenCode agent (`plan-agent`, `build-agent`, `validate-agent`, `review-agent`, `resolve-agent`, `research-agent`, `merge-agent`, `rebase-agent`), YAML frontmatter (`name`, `description`, `tools`) plus the system prompt body. Parsed at runtime by `demetra/services/agents/claude.py` (not installed to `~/.claude/agents`) and assembled into the `--agents` JSON passed to the `claude` CLI; Linear/web tools are injected by agent name, never a `mcp__linear__*` wildcard.
- `wiki/`: Persistent session knowledge base (pages, `INDEX.md` catalog + `By topic` clusters, `QUESTIONS.md` open discrepancies, 4 page types per `TEMPLATE.md` — see `wiki/README.md`; `wiki/archive/` holds retired pages preserved for provenance `[[...]]` links)

## Wiki

The `wiki/` directory is a persistent, compounding knowledge base: one Markdown page per session (debug chase, investigation, code review, or set of changes), cross-linked into a knowledge graph. Conventions and the page template: [wiki/README.md](wiki/README.md); the catalog of all pages: [wiki/INDEX.md](wiki/INDEX.md) (`## Pages` newest-first + `## By topic` clusters auto-maintained by `wiki-consistency`); open discrepancies tracked in [wiki/QUESTIONS.md](wiki/QUESTIONS.md).

- Before planning or building, skim `wiki/INDEX.md` for prior sessions on the same subsystem.
- For questions about past incidents, design decisions, or prior investigations, search the wiki first via the `wiki_search` MCP tool (browse the catalog with `wiki_list_pages`, fetch a full page with `wiki_get_page`).
- After a session, record it as a page using `wiki/TEMPLATE.md` and keep the index and cross-links current (see `.opencode/skills/wiki-sync/` and the installed `wiki-consistency`/`wiki-dedup`/`wiki-archive`/`wiki-agents-file` skills).

## Agent Harness

Demetra dispatches every agent call (plan, resolve, build, validate, review, review-fixes, merge, rebase, research) plus
session/token helpers through a facade rather than calling an agent CLI wrapper directly, so a project or user can switch
between two coding-agent backends:

- `settings.AGENT_HARNESS` (`opencode` | `claude`, default `opencode`) selects the backend; it also resolves per-project /
  per-user through `SessionEnvironment.agent_harness`, which raises `EnvironmentConfigError` for any other value.
- `demetra/services/agents/opencode.py`: the original `opencode run` CLI wrapper (unchanged).
- `demetra/services/agents/claude.py`: the `claude -p` CLI wrapper. Runs on the host OS using the current interactive
  `claude` login (keychain / `~/.claude`) — no API key plumbing. Builds `--agents` JSON at runtime from `.claude/agents/*.md`
  (tool allow/deny lists enforced both in the agent JSON and again via `--allowedTools`/`--disallowedTools`), an inline
  `--mcp-config` (Demetra MCP + Linear MCP, `--strict-mcp-config` so user-level MCP servers stay out), and
  `--output-format stream-json --verbose` parsed by `format_claude_stream_event`/`extract_claude_result`. Global
  `~/.claude/CLAUDE.md`, hooks and plugins load same as any interactive session — nothing scopes them out.
- `demetra/services/agents/harness.py`: the facade. Every function takes `environment: SessionEnvironment` (optional,
  defaulting to bare settings) and dispatches on `environment.agent_harness`; workflows and `services/vcs/{merge,rebase}.py`
  import only this facade, never `opencode.py`/`claude.py` directly. `review_agents(...)` fans the configured review models
  out concurrently (`environment.review_models`, a list of `ReviewModel(model, effort)` — Claude entries may carry a
  `model:effort` pair, OpenCode entries never do).
- Per-agent Claude models/effort live in `settings.CLAUDE` (`CLAUDE_PLAN_MODEL`/`CLAUDE_PLAN_EFFORT`, etc.), each
  overridable per project/user like the OpenCode models. `CLAUDE_REVIEW_MODELS` defaults to `["opus:xhigh"]`.
- **No turn cap:** the installed Claude CLI has no `--max-turns` flag and `maxTurns` in agent JSON/frontmatter does not
  bound a top-level `-p` run (verified empirically against the installed CLI, 2026-09-30). A per-run USD budget
  (`--max-budget-usd`, `settings.CLAUDE_MAX_BUDGET_USD` + per-agent `CLAUDE_<AGENT>_MAX_BUDGET_USD` overrides) is the real
  bound against a looping/runaway run instead — the result event's `subtype` becomes `error_max_budget_usd` when it fires.
  Combined with `CLAUDE_IDLE_TIMEOUT` (idle-stdout watchdog on the subprocess, 900s default, must be between 660s and
  `SUBPROCESS_TIMEOUT`) and the existing overall `SUBPROCESS_TIMEOUT`.
- **Session pinning:** `sessions.harness` (migration `add_sessions_harness_column`) pins the harness a session last ran
  under. On re-entry (`workflows/setup.py`), a stored harness that differs from the resolved one clears `session_id` and
  re-pins the harness (`reset_session_harness`) so a mid-ticket switch never resumes a foreign session id; the build plan
  is kept. This check runs on every re-entry, not only once.
- **No cross-agent `--resume`:** verified empirically (2026-09-30) that `--resume <id>` with a different `--agent` does
  NOT switch persona — Claude snapshots the first agent's system prompt for the life of the conversation and reuses it
  verbatim on every later request/resume, so resuming the plan agent's session under `build-agent` would silently keep
  answering as the plan agent (wrong tools, read-only). Unlike OpenCode, `workflows/build.py::run_build_step` therefore
  runs the build step under its own fresh session for Claude (`harness.new_session_id`, ignoring the plan's
  `context.session_id` entirely) and reuses that same id across every iteration of the build retry loop, so resuming
  stays safe (always the same agent). This id is scoped to build execution and token lookup only and is never
  persisted — `context.session_id` (`sessions.session_id`) stays the canonical, plan-linked id throughout, so a process
  restart simply starts a fresh build session rather than resuming a stale one. OpenCode is unaffected (`new_session_id`
  returns `None` for it, preserving the existing continued-session behavior).
- **Linear tool scope:** `CLAUDE_LINEAR_READ_TOOLS` / `CLAUDE_LINEAR_CREATE_TOOLS` (`demetra/library/constants.py`) list
  exact Linear MCP tool names (never a `mcp__linear__*` wildcard) — read-only tools for plan/resolve/research, plus
  create-issue/create-comment for research only. **The exact tool names have not been confirmed against a live,
  authenticated `linear` MCP session (`/mcp` in an interactive `claude` session) — verify before relying on them.**
- Out of scope for v1: Docker image support (host OS only), Cursor/CodeRabbit cleanup, a React UI toggle (the env editor
  already covers `AGENT_HARNESS`).

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

# Upgrade dependencies and pre-commit hooks
uv run uv-bump
uv sync --all-extras --dev
uv run pre-commit autoupdate
```

### Running Modules

From the project root, after creating a virtualenv and installing dependencies:

```bash
uv run main.py --project-name <project_name>
```

### Containerized Deploy

`make deploy` is the deploy path and runs the full app layer (Postgres, Redis, API, 4 workers, watcher, listener, RQ dashboard and a one-shot React build) on top of the `mantiby/demetra` image. The old systemd path (`configs/bootstrap.sh`, `configs/services/*.service`, `systemctl restart demetra-*`) was removed in `f5904d5` (2026-09-11).

Prerequisites: Docker Compose v2 (the `docker-up` target passes `--scale worker=4` so 4 workers run — the compose file declares `worker.deploy.replicas: 2` as a default at `docker-compose.yaml:102`; the `deploy` target uses `--scale worker=2` at `Makefile:31`); the `mantiby/demetra:latest` image (built from the local Dockerfile by `make docker-build`), and `docker-build` needs Docker BuildKit.

```bash
cp .env.docker.example .env.docker   # then fill in real values
make deploy                          # git pull + build + pull infra + migrate/react one-shots + up long-running (scale 2) + nginx reload
# pure-Docker path (no git pull / nginx reload):
make docker-build && make docker-up  # build image + up with 4 workers (Makefile:100-101); `postgres`/`redis`/`oven/bun` pulled automatically
```

## Language & Environment

- Python >=3.13.9, <3.14.0 (see `pyproject.toml`)
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
- Functions: `snake_case`; module-level private helpers use a leading `_` (e.g. `demetra/tools/wiki.py`, `demetra/tools/database.py`); external-CLI wrappers prefix the system name (`opencode_*`, `git_*`, `cursor_*`)
- Constants: `UPPER_SNAKE_CASE`; env-driven ones live in `demetra/settings.py`

**Architecture** (strict layering, no skipping):
- `demetra/library/` — pure: dataclasses, TypedDicts, exceptions, tables. No I/O.
- `demetra/services/<system>/` — one external system or cross-cutting area per subpackage (`agents/`, `auth/`, `daemons/`, `linear/`, `llm/`, `persistence/`, `quality/`, `runtime/`, `vcs/`, `wiki/`); `auth/`, `linear/`, `llm/`, `vcs/`, `wiki/` re-export through a facade `__init__.py`, while `agents/`, `daemons/`, `persistence/`, `quality/`, `runtime/` are plain packages imported by submodule path (e.g. `demetra.services.runtime.tui`). Subprocess wrappers return `tuple[int, str, str]` (`exit_code, stdout, stderr`).
- `demetra/workflows/<step>.py` — orchestrators; receive `Context`, call services. Entry points typically `run_<step>_*` (includes `review_fixes.py` for the `@demetra-ai fix review findings` listener flow and `research.py` for the `Research` label loop — creates related Linear ticket, persists `research_report`, uses `research` → `researched` steps). Workflows read env via `Context.environment` (`SessionEnvironment` in `demetra/library/models.py`: project → user-shared → settings fallback, `EnvironmentConfigError` on missing key; see `wiki/pages/2026-09-16-mnt-205-revise-merged-environment.md`).
- `demetra/api/<resource>.py` — FastAPI `router = APIRouter(...)`; thin, delegates to services.
- `demetra/tools/<system>.py` — MCP tool modules (`database.py`, `docstrings.py`, `projects.py`, `wiki.py` plus shared `search.py` tokenization) exposing `async def list_tools()` and `async def call_tool(name, arguments)`; dispatchers return a shared `ToolResult` (`demetra/tools/result.py`) carrying `content` + `is_error`. `demetra/tools/registry.py` aggregates them (database + docstrings + projects + wiki), re-exported through `demetra/tools/__init__.py`; `mcp_server.py` calls the package-level `list_tools` / `call_tool`.

**Do NOT use**: `print()` (use `print_message` from `demetra.services.runtime.tui`; sole exception: `mcp_server.py` startup banner to stderr), PEP 585 typing (`Tuple[X]/Optional[X]/List[X]/Dict[X]` — use PEP 604 `X | None` / `list[X]`), mutable default arguments (use `field(default_factory=...)`), inline comments and emojis in code, bare `except Exception:` (catch specific `OSError`/`RuntimeError` instead; the accepted uses are MCP `call_tool` dispatchers that `logger.exception`, workflow cleanup paths carrying `# noqa: BLE001`, daemon poll-loop guards (`demetra/watcher.py:40`, `demetra/listener.py:85`), LLM-call boundary guards that `logger.exception` and raise a typed error (`demetra/services/llm/openrouter.py`), and best-effort copy/cleanup guards that `logger.exception` (`demetra/services/auth/copy.py`, `demetra/services/runtime/project.py:312,323`)) and `# noqa` suppressions — check `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.per-file-ignores]`, `[tool.bandit]`, `[tool.ty.src]`) for the canonical list of allowed ignores/exclusions for `ruff`, `ty` and `bandit`; do not add new suppressions without updating config.

**Imports**: Always place imports at the top of the file (global scope). Local imports inside functions are permitted only in rare cases where they are necessary to resolve circular import dependencies.

**Feature flags**: `demetra/settings.py` defines `FEATURES` (`is_ruff_enabled`, `is_pytest_enabled` from `IS_RUFF_ENABLED` / `IS_PYTEST_ENABLED`, both default `False` — `demetra/workflows/lint.py` only runs `ruff`/`pytest` when package installed *and* flag `True`), `SEARCH` (shared wiki/docstring weights, limits; stop words live as `SEARCH_STOP_WORDS` in `demetra/library/constants.py`, consumed by `demetra/tools/search.py`), and `WIKI` budgets (`WIKI_LLM_BUDGET_FILES`/`_LINES`, `WIKI_DIFF_HUNK_CAP`/`_BUILD_PLAN_CAP`, `WIKI_REVALIDATION_ENABLED`), and `MAX_ATTEMPTS` (per-step retry budgets keyed by workflow — `run`/`plan`/`build`/`review`/`merge`/`rebase`/`listener`/`research`, each read from its `MAX_*_ATTEMPTS` env var). Lint/tests are opt-in.

## Testing Guidelines

- Use `pytest` for tests
- Tests live in `tests/` directory
- Run with `make test` or `uv run pytest tests/`
- Group test cases in classes named `Test<Feature>` (e.g. `TestWaitlistCliList`); do not use module-level `def test_*` functions for new tests (legacy module-level tests remain in `tests/test_allowlist_cli.py` and `tests/test_migrations.py`)

## Database Migrations

When creating Alembic migrations:

- Use descriptive names in snake_case (e.g., `add_users_table`, `drop_sessions_column`, `create_oauth_tokens_index`)
- Prefix with operation type: `add_`, `create_`, `drop_`, `alter_`, `remove_`, `rename_`
- Include the table name and what changed
- Example: `uv run alembic revision --autogenerate -m "add_user_keys_column"`

## Environment & Configuration

Environment is controlled primarily via `demetra/settings.py` and `.env`.

## Dependencies

Declared in `pyproject.toml` (core under `dependencies`, dev tooling under `[dependency-groups] dev`) and locked in `uv.lock`.

## External Dependencies

Demetra coordinates the following external tools:

- **OpenCode**: AI coding assistant for planning and building features
- **Claude Code**: alternative agent harness for planning and building features, selected via `AGENT_HARNESS=claude` (see [Agent Harness](#agent-harness)); runs on the host OS, `claude -p` CLI
- **Cursor**: AI-powered code review tool
- **CodeRabbit**: Alternative AI code review tool
- **Linear**: Issue tracking via GraphQL API
- **GitHub**: PR creation and notification-driven merge/rebase/`fix review findings` triggers (`demetra/listener.py` → `demetra/services/daemons/listener.py` → `demetra/workflows/review_fixes.py`)
- **OpenRouter**: LLM API for plan extraction, review and wiki summarisation, and PR description generation (`demetra/services/llm/openrouter.py`)
- **Playwright**: browser automation via MCP (`opencode.json` `mcp.Playwright`; no React E2E suite — frontend tests are vitest component tests)
- **LangSmith**: tracing plugin for OpenCode (`opencode.json` `plugins`)

## Security Guidelines

- Never commit secrets, passwords, or API tokens
- Configure sensitive values via environment variables
- Run `bandit` periodically or in CI
- Validate any external input before using it in system calls or network operations

## AI Behavior

Response style — concise and minimal: working code without boilerplate or unnecessary explanation, clear naming over comments, no tangential suggestions.
