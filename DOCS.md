# AGENTS.md

Development guidelines for Demetra - AI agents should reference this file.

## Project Overview

Demetra is a coding workflow orchestration tool that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

## Project Structure

```
demetra/
├── __init__.py
├── exceptions.py                  # Custom exception classes
├── models.py                     # LinearIssue dataclass
├── settings.py                   # Settings and configuration
└── services/
    ├── __init__.py
    ├── coderabbit.py             # CodeRabbit review agent
    ├── cursor.py                # Cursor review agent
    ├── database.py              # SQLite operations
    ├── filesystem.py            # Filesystem utilities
    ├── flow.py                  # Workflow orchestration
    ├── git.py                   # Git worktree operations
    ├── graphql.py              # GraphQL client
    ├── linear.py                # Linear API integration
    ├── lint.py                  # Code linting
    ├── opencode.py              # OpenCode agents
    ├── subprocess.py            # Subprocess utilities
    ├── test.py                  # Test runner
    ├── tui.py                   # Rich console output
    ├── utils.py                 # Async utilities
    ├── queries/
    │   ├── get_todo_issues.gql
    │   ├── list_states.gql
    │   └── update_issue_status.gql
    └── tui/
        └── header.txt
main.py                          # Entry point
tests/                           # Test suite
```

## Installation

### Dependencies

```bash
uv sync --all-extras --dev
```

### OpenCode CLI

```bash
curl -fsSL https://opencode.ai/install | bash
source ~/.bashrc
opencode auth login
```

### Cursor CLI

```bash
curl https://cursor.com/install -fsS | bash
agent login
```

### CodeRabbit CLI

```bash
curl -fsSL https://cli.coderabbit.ai/install.sh | sh
source ~/.bashrc
coderabbit auth login
```

### GitHub CLI

Follow [installation guide](https://github.com/cli/cli?tab=readme-ov-file#installation), then:

```bash
gh auth login
```

### Bun (for React app)

```bash
curl -fsSL https://bun.com/install | bash
```

## Git Workflow

Follow Git Flow strictly:

### Main Branch
- `master` always contains production-ready code
- Never commit directly to `master`
- Never use `git push --force` on `master`

### Feature Branches
- Naming: `<agent>/feature/<issue-id>-<description>`
- Example: `opencode/feature/DEMETRA-10-add-login`
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

## Testing

- pytest in `tests/` directory
- Run: `make test` or `uv run pytest tests/`

## Database Migrations

Alembic migrations:

```bash
uv run alembic revision --autogenerate -m "add_user_keys_column"
```

Naming: snake_case with operation prefix (`add_`, `create_`, `drop_`, etc.)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECTS_PATH` | Projects directory | `$HOME/www` |
| `DB_PATH` | SQLite database | `$HOME/.demetra/demetra.sqlite3` |
| `LINEAR_API_KEY` | Linear API key | - |
| `LINEAR_API_URL` | Linear GraphQL URL | `https://api.linear.app/graphql` |
| `LINEAR_TEAM_ID` | Linear team ID | - |
| `LINEAR_STATE_TODO_ID` | TODO state ID | - |
| `LINEAR_STATE_IN_PROGRESS_ID` | In Progress state | - |
| `LINEAR_STATE_IN_REVIEW_ID` | In Review state | - |
| `OPENCODE_PATH` | OpenCode binary | `$HOME/.opencode/bin/opencode` |
| `OPENCODE_MODEL` | OpenCode model | `opencode/minimax-m2.5-free` |
| `CURSOR_PATH` | Cursor binary | `$HOME/.local/bin/cursor-agent` |
| `CODERABBIT_PATH` | CodeRabbit binary | `$HOME/.local/bin/coderabbit` |
| `GIT_PATH` | git binary | `/usr/bin/git` |
| `GIT_WORKTREE_PATH` | Worktrees path | `$HOME/.demetra/worktrees/` |

## Dependencies

**Core**: asyncio, aiofiles, aiohttp, psycopg, python-slugify, rich, langchain-groq, langchain-core

**Development**: pytest, pytest-asyncio, debugpy, ipython, pre-commit, ty, uv-bump

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

GitHub Actions workflow (`.github/workflows/checks.yml`):

```bash
uv sync --locked          # Install dependencies
uv run pre-commit run     # Lint all files
```

## Makefile Targets

```bash
make run-chimera       # Run on 'chimera'
make run-demetra       # Run on 'demetra'
make run-odin         # Run on 'odin'
make run-coruscant    # Run on 'coruscant'
make check            # Type check + pre-commit
make test             # Run tests
make update           # Upgrade deps + hooks
```

## GitHub OAuth Setup

For API GitHub login:

1. GitHub Settings → Developer settings → OAuth Apps → New OAuth App
2. Configure:
   - Name: Demetra
   - Homepage: `https://demetra.manti.by`
   - Callback: `https://demetra.manti.by/api/v1/github/callback`
3. Set environment variables:

```bash
export GITHUB_CLIENT_ID="your_client_id"
export GITHUB_CLIENT_SECRET="your_client_secret"
export GITHUB_REDIRECT_URI="https://demetra.manti.by/api/v1/github/callback"
export JWT_SECRET_KEY="your_secure_random_key"
```

JWT secret should be at least 32 characters.