# AGENTS.md

## Project Overview

Demetra is an autonomous coding platform that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

## Project Structure

- `main.py`: CLI entry point and supervisor orchestration
- `demetra/settings.py`: Core configuration and environment variables
- `demetra/library/`: Pure data layer (dataclasses, TypedDicts, exceptions, tables, constants)
- `demetra/services/`: External system integrations (Linear, GitHub, OpenCode, etc.)
- `demetra/queries/`: GraphQL queries
- `demetra/workflows/`: Workflow orchestration steps
- `demetra/api/`: FastAPI REST endpoints
- `demetra/tools/`: MCP tool definitions
- `demetra/prompts/`: LLM prompt templates
- `demetra/templates/`: Linear failure-comment message templates (`build_failed`, `pr_creation_failed`, `review_failed`, `wiki_failed`)
- `demetra/app.py`: FastAPI application
- `demetra/mcp_server.py`: MCP server
- `demetra/watcher.py` / `demetra/listener.py` / `demetra/worker.py`: Thin entrypoints (logic lives in `demetra/services/daemons/`; watcher = Linear TODO poller, listener = GitHub notifications)
- `react/`: React frontend (Vite + TypeScript)
- `migrations/`: Alembic database migrations
- `alembic.ini`: Alembic configuration (drives the migration commands)
- `tests/`: Comprehensive test suite (55 `test_*.py` files, 57 total with `__init__.py`/`conftest.py`)
- `configs/`: Systemd service files, nginx config, Docker entrypoint (`configs/docker-entrypoint.sh`, plus `bootstrap.sh`/`proxy.params`/`services/`)
- `wiki/audits/workflow-state-machine.html`: Interactive Mermaid diagram of the workflow state machine (static asset)
- `Dockerfile`, `docker-compose.yaml`, `.dockerignore`: containerized deploy (api/worker/watcher/listener/rq-dashboard + one-shot React build; see `make docker-deploy`)
- `.github/`: GitHub Actions CI (`checks.yml`)
- `.opencode/`: OpenCode agent and skill definitions
- `opencode.json`: OpenCode agent toolchain configuration (MCP servers, plugins)
- `wiki/`: Persistent session knowledge base (pages, index, conventions — see `wiki/README.md`; `wiki/archive/` holds retired pages preserved for provenance `[[...]]` links)

## Wiki

The `wiki/` directory is a persistent, compounding knowledge base: one Markdown page per session (debug chase, investigation, code review, or set of changes), cross-linked into a knowledge graph. Conventions and the page template: [wiki/README.md](wiki/README.md); the catalog of all pages: [wiki/INDEX.md](wiki/INDEX.md).

- Before planning or building, skim `wiki/INDEX.md` for prior sessions on the same subsystem.
- For questions about past incidents, design decisions, or prior investigations, search the wiki first via the `wiki_search` MCP tool (browse the catalog with `wiki_list_pages`, fetch a full page with `wiki_get_page`).
- After a session, record it as a page using `wiki/TEMPLATE.md` and keep the index and cross-links current (see the `wiki-*` skills in `.opencode/skills/`).

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

Alternative deployment path that runs the full app layer (Postgres, Redis, API, 4 workers, watcher, listener, RQ dashboard and a one-shot React build) on top of the `mantiby/demetra` image. The systemd `make deploy` path is untouched.

Prerequisites: Docker Compose v2 (the `docker-up`/`docker-deploy` targets pass `--scale worker=4` so 4 workers run; the compose file does not declare `deploy.replicas`), the `mantiby/demetra:latest` image (built from the local Dockerfile by `make docker-build`, which `docker-deploy` runs as a prerequisite; the `postgres`/`redis`/`oven/bun` images are pulled automatically), and `docker-build` needs Docker BuildKit.

```bash
cp .env.docker.example .env.docker   # then fill in real values
make docker-deploy                   # build image + pull infra + migrate/react one-shots + up long-running + ps
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
- Classes: `PascalCase`; dataclasses in `library/models.py`, TypedDicts in `library/types.py`
- Functions: `snake_case`; module-level private helpers use a leading `_` (e.g. `demetra/tools/wiki.py`, `demetra/tools/database.py`); external-CLI wrappers prefix the system name (`opencode_*`, `git_*`, `cursor_*`)
- Constants: `UPPER_SNAKE_CASE`; env-driven ones live in `demetra/settings.py`

**Architecture** (strict layering, no skipping):
- `demetra/library/` — pure: dataclasses, TypedDicts, exceptions, tables. No I/O.
- `demetra/services/<system>/` — one external system or cross-cutting area per subpackage (`agents/`, `auth/`, `daemons/`, `linear/`, `llm/`, `persistence/`, `quality/`, `runtime/`, `vcs/`, `wiki/`); each subpackage's `__init__.py` acts as the public facade. Subprocess wrappers return `tuple[int, str, str]` (`exit_code, stdout, stderr`).
- `demetra/workflows/<step>.py` — orchestrators; receive `Context`, call services. Entry points typically `run_<step>_*` (includes `review_fixes.py` for the `@demetra-ai fix review findings` listener flow).
- `demetra/api/<resource>.py` — FastAPI `router = APIRouter(...)`; thin, delegates to services.
- `demetra/tools/<system>.py` — MCP tool modules (`database.py`, `projects.py`, `wiki.py`) exposing `async def list_tools()` and `async def call_tool(name, arguments)`; dispatchers return a shared `ToolResult` (`demetra/tools/result.py`) carrying `content` + `is_error`. `demetra/tools/registry.py` aggregates them, re-exported through `demetra/tools/__init__.py`; `mcp_server.py` calls the package-level `list_tools` / `call_tool`.

**Do NOT use**: `print()` (use `print_message` from `demetra.services.runtime.tui`; sole exception: `mcp_server.py` startup banner to stderr), PEP 585 typing (`Tuple[X]/Optional[X]/List[X]/Dict[X]` — use PEP 604 `X | None` / `list[X]`), mutable default arguments (use `field(default_factory=...)`), inline comments and emojis in code, bare `except Exception:` (catch specific `OSError`/`RuntimeError` instead) and `# noqa` suppressions — check `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.per-file-ignores]`, `[tool.bandit]`, `[tool.ty.src]`) for the canonical list of allowed ignores/exclusions for `ruff`, `ty` and `bandit`; do not add new suppressions without updating config.

**Imports**: Always place imports at the top of the file (global scope). Local imports inside functions are permitted only in rare cases where they are necessary to resolve circular import dependencies.

**Feature flags**: `demetra/settings.py` defines a `FEATURES` dict (`is_ruff_enabled`, `is_pytest_enabled`) read from `IS_RUFF_ENABLED` / `IS_PYTEST_ENABLED` env vars (both default `False`). `demetra/workflows/lint.py` only runs `ruff` / `pytest` when both the package is installed *and* the matching flag is `True`, so lint and tests are opt-in.

## Testing Guidelines

- Use `pytest` for tests
- Tests live in `tests/` directory
- Run with `make test` or `uv run pytest tests/`
- Group test cases in classes named `Test<Feature>` (e.g. `TestWaitlistCliList`); do not use module-level `def test_*` functions

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
- **Cursor**: AI-powered code review tool
- **CodeRabbit**: Alternative AI code review tool
- **Linear**: Issue tracking via GraphQL API
- **GitHub**: PR creation and notification-driven merge/rebase/`fix review findings` triggers (`demetra/listener.py` → `demetra/services/daemons/listener.py` → `demetra/workflows/review_fixes.py`)
- **Groq**: legacy LLM API, fully superseded by OpenRouter (`demetra/services/llm/groq.py` retained but unused)
- **OpenRouter**: LLM API for plan extraction, review and wiki summarisation, and PR description generation (`demetra/services/llm/openrouter.py`)

## Security Guidelines

- Never commit secrets, passwords, or API tokens
- Configure sensitive values via environment variables
- Run `bandit` periodically or in CI
- Validate any external input before using it in system calls or network operations

## AI Behavior

Response style — concise and minimal: working code without boilerplate or unnecessary explanation, clear naming over comments, no tangential suggestions.
