# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Demetra is a coding workflow orchestration tool that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow using git worktrees.

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync --all-extras --dev

# Install and setup external tools (one-time setup)
curl -fsSL https://opencode.ai/install | bash && source ~/.bashrc && opencode auth login
curl https://cursor.com/install -fsS | bash && agent login
curl -fsSL https://cli.coderabbit.ai/install.sh | sh && source ~/.bashrc && coderabbit auth login
gh auth login  # Install gh CLI first from https://github.com/cli/cli
```

### Running the Application
```bash
# Run workflow on specific projects
make run-chimera    # chimera project
make run-demetra    # demetra project
make run-odin       # odin project
make run-coruscant  # coruscant project

# Or manually with project name
uv run main.py --project-name <project_name>

# Run specific Linear task
uv run main.py --project-name <project_name> --task-id <linear_task_id>
```

### Development Tools
```bash
# Run all checks (type checking + pre-commit)
make check

# Run tests
make test
uv run pytest tests/

# Run single test file
uv run pytest tests/test_specific.py

# Update dependencies and hooks
make update

# Full CI pipeline
make ci  # equivalent to: pip check test
```

### FastAPI Ticket Creation API
```bash
# Development mode
make api              # Start the FastAPI server for ticket creation
make api-dev          # Start in development mode (with auto-reload)
make test-api         # Test the API
make example          # Run example usage

# Production systemd service
make service-install  # Install systemd service (requires sudo)
make service-start    # Start the service
make service-stop     # Stop the service
make service-restart  # Restart the service
make service-status   # Check service status
make service-logs     # View service logs
make service-test     # Test service health
```

### Code Quality
```bash
# Linting and formatting (via pre-commit)
uv run pre-commit run --all-files

# Type checking
uv run ty check

# Security scanning
bandit -c pyproject.toml -r demetra/
```

## Architecture Overview

### Core Workflow Steps
The application follows a structured workflow pipeline:

1. **Setup** (`setup.py`) - Task retrieval from Linear and worktree creation
2. **Planning** (`plan.py`) - Feature planning using OpenCode plan agent
3. **Building** (`build.py`) - Feature implementation using OpenCode build agent
4. **Review** (`review.py`) - Code review using Cursor or CodeRabbit
5. **Cleanup** (`cleanup.py`) - Commit, push, and worktree cleanup

### Key Components

**Main Entry Point**: `main.py` - Orchestrates the entire workflow with error handling

**Core Modules**:
- `demetra/models.py` - Data structures (`LinearTask`, `Session`, `Context`)
- `demetra/settings.py` - Configuration and environment variables
- `demetra/exceptions.py` - Custom exception hierarchy

**Service Layer** (`demetra/services/`):
- `linear.py` - Linear API integration for task management
- `opencode.py` - OpenCode AI agent integration (plan/build)
- `cursor.py` - Cursor AI code review integration
- `coderabbit.py` - CodeRabbit AI code review integration (alternative to Cursor)
- `git.py` - Git worktree management and operations
- `database.py` - SQLite persistence for sessions and state
- `graphql.py` - GraphQL client for Linear API
- `tui.py` - Terminal UI with Rich library styling
- `subprocess.py` - Async subprocess execution utilities

### Configuration

Environment variables (via `.env` or shell):
- `PROJECTS_PATH` - Path to projects directory (default: `$HOME/www`)
- `LINEAR_API_KEY` - Linear API key (required)
- `GROQ_API_KEY` - Groq API key for FastAPI ticket creation (required for API)
<<<<<<< Updated upstream
- `LINEAR_TEAM_ID` - Linear team ID (required)
- `OPENCODE_PATH` - Path to OpenCode binary
- `LINEAR_API_URL` - Linear GraphQL API URL (hardcoded: `https://api.linear.app/graphql`)
- `LINEAR_TEAM_ID` - Linear team ID (required)
- `LINEAR_STATE_TODO_ID` - Linear TODO state ID
- `LINEAR_STATE_IN_PROGRESS_ID` - Linear In Progress state ID
- `LINEAR_STATE_IN_REVIEW_ID` - Linear In Review state ID
- `OPENCODE_PATH` - Path to OpenCode binary
- `OPENCODE_MODEL` - OpenCode model to use (default: `opencode/minimax-m2.5-free`)
- `CURSOR_PATH` - Path to Cursor binary
- `CODERABBIT_PATH` - Path to CodeRabbit binary
- `DB_PATH` - SQLite database path (default: `$HOME/.demetra/demetra.sqlite3`)
- `GIT_WORKTREE_PATH` - Git worktrees path (default: `$HOME/.demetra/worktrees/`)

Linear state IDs are project-specific and configurable via environment variables.

### Git Worktree Strategy

The application uses git worktrees to isolate feature work:
- Creates temporary worktrees in `GIT_WORKTREE_PATH`
- Each task gets its own branch and isolated working directory
- Automatic cleanup after workflow completion
- Prevents conflicts between concurrent development work

### AI Agent Integration

**OpenCode**: Used for planning and building features
- Plan agent creates implementation strategies
- Build agent executes the implementation
- Configurable model via `OPENCODE_MODEL`

**Cursor/CodeRabbit**: Used for code review
- Reviews implementation for quality and correctness
- Provides feedback for iteration if needed
- CodeRabbit is more powerful but more expensive alternative

**FastAPI Ticket Creator**: HTTP API for creating Linear tickets from raw text
- Uses Groq LLM to structure unstructured text into proper tickets
- Automatically creates titles, descriptions, technical requirements, and acceptance criteria
- Integrates with existing Linear workflow
- Available at `/create-ticket` endpoint when API server is running

### Database Schema

SQLite database tracks:
- Workflow sessions with build plans and status
- Task assignments and completion state
- Linear posting status to avoid duplicate comments

### Error Handling

Custom exception hierarchy in `exceptions.py`:
- `DemetraError` - Base exception
- `UserCancelledError` - User-initiated cancellation
- `AutoCancelledError` - Automatic cancellation
- `InfiniteLoopError` - Loop detection in workflow

## Testing

Comprehensive test suite in `tests/` covering:
- Unit tests for individual services
- Integration tests for workflow components
- Database operations and state management
- External tool integrations (mocked)

Test configuration in `pyproject.toml` with pytest-asyncio for async test support.

## Code Standards

- **Python**: >=3.13.9, <3.14.0
- **Formatting**: Ruff formatter with 120-character line length
- **Linting**: Ruff with extensive rule set (pycodestyle, pyflakes, bandit, etc.)
- **Type Checking**: ty (enabled via `make check`)
- **Pre-commit**: Automated formatting, linting, and security checks
- **Import Organization**: isort with custom "demetra" section

## Dependencies

**Core**: asyncio, aiofiles, aiohttp, aiosqlite, python-slugify, rich
**AI/LLM**: langchain-groq, langchain-core
**Development**: pytest, pytest-asyncio, debugpy, ipython, pre-commit
