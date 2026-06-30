# DOCS.md

Extended developer documentation for Demetra. AI agents should reference **AGENTS.md** for development guidelines and conventions.

## Project Overview

Demetra is a coding workflow orchestration tool that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

## Project Structure

Root:

```
main.py                          # CLI entry point and supervisor orchestration
pyproject.toml                   # Project metadata, deps, tool config
opencode.json                    # OpenCode LSP/MCP configuration
Makefile                         # Build/run/test/deploy targets
Dockerfile                       # Multi-stage container build
AGENTS.md                        # AI agent development guidelines
README.md                        # Project README
```

Core Python package (`demetra/`):

```
demetra/
├── app.py                       # FastAPI application
├── mcp_server.py                # MCP server
├── watcher.py                   # Linear TODO poller
├── listener.py                  # GitHub notification listener
├── worker.py                    # RQ worker
├── settings.py                  # Core configuration and environment variables
├── api/                         # FastAPI REST endpoints
│   ├── github.py                #   GitHub OAuth login/callback/me/logout
│   ├── projects.py              #   CRUD projects + environment vars
│   ├── sessions.py              #   List/delete sessions
│   ├── users.py                 #   Update user API keys
│   ├── watcher.py               #   WebSocket log streaming
│   └── webhooks.py              #   GitHub webhook receiver
├── library/                     # Pure data layer (no I/O)
│   ├── models.py                #   Dataclasses (LinearTask, Session, Context, Project, etc.)
│   ├── types.py                 #   TypedDicts (config types)
│   ├── tables.py                #   SQLAlchemy table definitions
│   ├── exceptions.py            #   Custom exception classes
│   └── header.py                #   ASCII art banner
├── services/                    # External system integrations
│   ├── auth.py                  #   GitHub OAuth + JWT
│   ├── auth_copy.py             #   Copy auth from parent OS
│   ├── coderabbit.py            #   CodeRabbit review agent
│   ├── constants.py             #   PostgreSQL reserved words
│   ├── cursor.py                #   Cursor review agent
│   ├── database.py              #   SQLAlchemy async DB operations
│   ├── encryption.py            #   Fernet encryption for secrets
│   ├── filesystem.py            #   Project root resolution
│   ├── flow.py                  #   Interactive user input
│   ├── git.py                   #   Git worktree operations
│   ├── github.py                #   GitHub CLI + webhook verification
│   ├── graphql.py               #   Linear GraphQL client
│   ├── groq.py                  #   Groq LLM (LangChain) integrations
│   ├── linear.py                #   Linear API operations
│   ├── lint.py                  #   Ruff linter commands
│   ├── listener.py              #   GitHub notification polling
│   ├── merge.py                 #   Git merge + conflict resolution
│   ├── oauth.py                 #   Linear OAuth token management
│   ├── opencode.py              #   OpenCode agent runners
│   ├── parser.py                #   NumberedList output parser
│   ├── project.py               #   Project setup (clone, DB create, version bump)
│   ├── prompt.py                #   Prompt loader
│   ├── queue.py                 #   RQ task queue
│   ├── rebase.py                #   Git rebase + conflict resolution
│   ├── subprocess.py            #   Async subprocess runner
│   ├── test.py                  #   Pytest runner
│   ├── tui.py                   #   Rich console output
│   └── utils.py                 #   Async stream reader, session logging
├── queries/                     # GraphQL queries
│   ├── get_all_issues.gql
│   ├── get_issue_by_id.gql
│   ├── create_issue.gql
│   ├── create_issue_comment.gql
│   └── update_issue_status.gql
├── prompts/                     # LLM prompt templates (Markdown)
│   ├── analyze_ticket.md
│   ├── extract_questions.md
│   ├── generate_pr_description.md
│   ├── merge_agent.md
│   ├── rebase_agent.md
│   ├── resolve_questions.md
│   ├── review_agent.md
│   ├── summarize_plan.md
│   └── summarize_review.md
├── tools/                       # MCP tool definitions
│   ├── database.py              #   DB query tools
│   └── projects.py              #   Log file tools
└── workflows/                   # Workflow orchestration steps
    ├── setup.py                 #   Workflow setup (load project, create worktree)
    ├── plan.py                  #   Plan agent + question resolution
    ├── resolve.py               #   Resolve agent for questions
    ├── build.py                 #   Build loop (build agent -> review -> lint -> test)
    ├── review.py                #   Multi-model review agents
    ├── lint.py                  #   Run ruff + pytest
    ├── cleanup.py               #   Commit, push, create PR, cleanup worktree
    ├── merge.py                 #   Merge workflow
    ├── rebase.py                #   Rebase workflow
    └── postprocess.py           #   Post-processing with ruff
```

Other directories:

```
react/                           # React frontend (Vite + TypeScript)
migrations/                      # Alembic database migrations
tests/                           # Test suite (40+ pytest files)
configs/                         # Systemd service files, nginx config
scripts/                         # Utility scripts (LLM parser benchmark)
.opencode/                       # OpenCode agent definitions
.github/workflows/               # CI (pre-commit checks)
```

## Installation

### Dependencies

```bash
uv sync --all-extras --dev
```

### OpenCode CLI

```bash
curl -fsSL https://opencode.ai/install | bash
opencode auth login
```

### Cursor CLI

```bash
curl https://cursor.com/install -fsS | bash
cursor auth login
```

### CodeRabbit CLI

```bash
curl -fsSL https://cli.coderabbit.ai/install.sh | sh
coderabbit auth login
```

### GitHub CLI

Follow [installation guide](https://github.com/cli/cli?tab=readme-ov-file#installation), then:

```bash
gh auth login
```

### Bun (for React app)

```bash
curl -fsSL https://bun.sh/install | bash
```

## Git Workflow

Follow Git Flow strictly:

### Main Branch
- `master` always contains production-ready code
- Never commit directly to `master`
- Never use `git push --force` on `master`

### Feature Branches
- Naming: `<agent-name>/feature/<issue-id>-<descriptive-name>`
- Example: `opencode/feature/DEMETRA-10-add-user-authentication`
- Use [Conventional Commits](https://www.conventionalcommits.org): `feat:`, `fix:`, `docs:`
- Run tests before committing

### Pull Requests
- Open PR for every completed feature
- PRs must pass CI and review before merge

## Linear Workflow

- TODO → In Progress: Start implementation
- Feature complete + PR created → In Review
- PR approved + merged → Done
- Branch closed without merge → Closed

## Language & Environment

- Python >=3.13.9, <3.14.0
- PEP 8 style (120 char line limit via Ruff)
- Type hints for public APIs
- f-strings only (no `.format()` or `%`)
- Comprehensions over `map`/`filter` where clearer
- `pathlib.Path` over `os.path`
- Named arguments in function calls

## Code Style & Tooling

Pre-configured in `pyproject.toml`:

- **Ruff**: Linting + import sorting
- **Bandit**: Security checks
- **pre-commit**: Hooks before commits
- **ty**: Type checking

Run manually:

```bash
uv run pre-commit run --all-files
uv run ruff check .
uv run ty check
uv run bandit -c pyproject.toml .
```

### Makefile Targets

```bash
make run-demetra          # Run workflow on 'demetra' (--no-auto)
make run-demetra-auto     # Run workflow on 'demetra' (--auto --plan-loop)
make run-odin             # Run workflow on 'odin' (--no-auto)
make run-coruscant        # Run workflow on 'coruscant' (--no-auto)
make run-mgallery-auto    # Run workflow on 'mgallery' (--auto --plan-loop)
make check                # Type check + pre-commit hooks
make install              # Install dependencies
make update               # Upgrade dependencies and pre-commit hooks
make test                 # Run tests
make test-cov             # Run tests with coverage (65% threshold)
make ci                   # Shorthand: install check test react-build react-test
make deploy               # Pull, sync, migrate, build React, restart services
make migrate              # Run Alembic migrations
make uvicorn              # Start FastAPI via uvicorn (port 8081)
make fastapi              # Start FastAPI dev server
make mcp                  # Start MCP server
make worker               # Start RQ worker
make watcher              # Start Linear TODO poller
make react                # Start React dev server
make docker-build         # Build amd64 Docker image
make docker-build-arm     # Build arm64 Docker image
```

## Testing

- pytest in `tests/` directory
- Run: `make test` or `uv run pytest tests/`

## Database Migrations

Alembic migrations:

```bash
uv run alembic revision --autogenerate -m "add_user_keys_column"
```

Naming: snake_case with operation prefix (`add_`, `create_`, `drop_`, etc.)

## Environment & Configuration

Environment is controlled primarily via `demetra/settings.py` and `.env`.

### Database

- `DB_HOST`: PostgreSQL host (default: `localhost`)
- `DB_PORT`: PostgreSQL port (default: `5432`)
- `DB_USER`: PostgreSQL user (default: `demetra`)
- `DB_NAME`: PostgreSQL database name (default: `demetra`)
- `DB_PASSWORD`: PostgreSQL password (required)
- `REDIS_URL`: Redis connection URL (default: `redis://localhost:6379/1`)
- `SECRET_KEY`: General secret key
- `ENCRYPTION_SALT`: Salt for Fernet encryption of secrets

### Linear

- `LINEAR_CLIENT_ID`: Linear OAuth client ID
- `LINEAR_CLIENT_SECRET`: Linear OAuth client secret
- `LINEAR_OAUTH_SCOPE`: OAuth scope (default: `read,write,comments:create`)
- `LINEAR_TEAM_ID`: Linear team ID
- `LINEAR_FEATURE_LABEL_ID`: Feature label ID for ticket filtering
- `LINEAR_FILTER_LABELS`: Comma-separated labels to filter by
- `LINEAR_STATE_PRD_ID`, `LINEAR_STATE_TODO_ID`, `LINEAR_STATE_IN_PROGRESS_ID`, `LINEAR_STATE_IN_REVIEW_ID`, `LINEAR_STATE_AWAITING_INPUT_ID`, `LINEAR_STATE_DONE_ID`: Linear workflow state IDs
- `LINEAR_DEFAULT_STATE_ID`: Default state ID for new issues

### OpenCode

- `OPENCODE_PATH`: Path to CLI binary (default: `$HOME/.opencode/bin/opencode`)
- `OPENCODE_PLAN_MODEL`: Model for planning (default: `opencode/minimax-m2.5-free`)
- `OPENCODE_RESOLVE_MODEL`: Model for resolving questions (default: `opencode/minimax-m2.5-free`)
- `OPENCODE_BUILD_MODEL`: Model for building (default: `opencode/minimax-m2.5-free`)
- `OPENCODE_REVIEW_MODELS`: Comma-separated models for review (default: `opencode/big-pickle,opencode/minimax-m2.5-free`)

### Tools

- `CURSOR_PATH`: Path to Cursor CLI binary (default: `$HOME/.local/bin/cursor-agent`)
- `CODERABBIT_PATH`: Path to CodeRabbit CLI binary (default: `$HOME/.local/bin/coderabbit`)
- `UV_PATH`: Path to UV binary (default: `$HOME/.local/bin/uv`)
- `GIT_PATH`: Path to git binary (default: `/usr/bin/git`)
- `GIT_WORKTREE_PATH`: Path for git worktrees (default: `$HOME/.demetra/worktrees/`)
- `GH_PATH`: Path to GitHub CLI binary (default: `/usr/bin/gh`)

### GitHub OAuth

- `GITHUB_CLIENT_ID`: GitHub OAuth app client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth app client secret
- `GITHUB_REDIRECT_URI`: OAuth callback URL (default: `https://demetra.manti.by/github/callback`)
- `GITHUB_WEBHOOK_SECRET`: Secret for verifying GitHub webhooks
- `GITHUB_TOKEN`: GitHub personal access token

### JWT

- `JWT_SECRET_KEY`: Secret key for JWT token signing (min 32 characters)
- Algorithm: `HS256`, expiration: 14 days

### Groq

- `GROQ_API_KEY`: API key for Groq LLM
- `GROQ_MODEL`: Model to use (default: `llama-3.1-8b-instant`)

### Paths

- `PROJECTS_PATH`: Base path for project directories (default: `$HOME/www`)
- `WORKTREE_PATH`: Git worktree base path (default: `$HOME/.demetra/projects`)
- `LOG_PATH`: Log file path (default: `/var/log/demetra/demetra.log`)
- `PARENT_HOME`: Optional parent OS home directory for auth copying

### Limits

- `MAX_BUILD_ATTEMPTS`: Max build iterations (default: `50`)
- `MAX_REVIEW_ATTEMPTS`: Max review iterations (default: `10`)
- `MAX_MERGE_ATTEMPTS`: Max merge attempts (default: `10`)
- `MAX_REBASE_ATTEMPTS`: Max rebase attempts (default: `10`)
- `MAX_PLAN_ATTEMPTS`: Max plan/resolve loop iterations (default: `30`)
- `MAX_RUN_ATTEMPTS`: Max workflow run attempts (default: `3`)
- `SUBPROCESS_TIMEOUT`: Subprocess timeout in seconds (default: `1800`)
- `WATCHER_POLL_INTERVAL`: Linear poll interval in seconds (default: `60`)
- `LISTENER_POLL_INTERVAL`: GitHub notification poll interval in seconds (default: `60`)

### Other

- `DEBUG`: Enable debug mode (`true`/`false`, default: `false`)
- `DEFAULT_USER_ID`: Default user ID for CLI workflows

## Dependencies

**Core**: aiofiles, aiohttp, alembic, asyncpg, fastapi, langchain-groq, langchain-core, mcp, psycopg, pydantic, python-jose, python-slugify, redis, rich, rq, rq-dashboard, ruff, sqlalchemy, uvicorn, websockets

**Development**: bandit, debugpy, faker, ipython, pytest, pytest-asyncio, pytest-cov, pre-commit, ty, uv-bump

## External Tools

Demetra coordinates:

- **OpenCode**: AI planning and building
- **Cursor**: AI code review
- **CodeRabbit**: Alternative review (more powerful, more expensive)
- **Linear**: Issue tracking via GraphQL

## Security

- Never commit secrets/tokens
- Use environment variables for sensitive data
- Run `bandit` in CI
- Validate external input before system calls

## CI/CD

GitHub Actions workflow (`.github/workflows/checks.yml`) — runs on push and pull_request:

```bash
uv sync --locked --all-extras --dev     # Install dependencies
uv run pre-commit run --all-files        # Lint all files
```

## GitHub OAuth Setup

For API GitHub login:

1. GitHub Settings → Developer settings → OAuth Apps → New OAuth App
2. Configure:
   - Name: Demetra
   - Homepage: `https://demetra.manti.by`
   - Callback: `https://demetra.manti.by/github/callback`
3. Set environment variables:

```bash
export GITHUB_CLIENT_ID="your_client_id"
export GITHUB_CLIENT_SECRET="your_client_secret"
export GITHUB_REDIRECT_URI="https://demetra.manti.by/github/callback"
export JWT_SECRET_KEY="your_secure_random_key"
```

JWT secret should be at least 32 characters.
