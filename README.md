# Demetra

An autonomous coding platform that coordinates multiple AI agents to automate software development. Integrates Linear (issues), OpenCode (plan/build/resolve/review), with automatic linting (Ruff) and testing (pytest).

![DAG Diagram](/media/interface.jpg)

## Features

- **Workflow Orchestration**: Coordinated development from task to a pull request.
- **OpenCode Integration**: AI-powered planning, building and review.
- **Build Loop**: Automatically resolve review agents findings, lint and test errors.
- **Linear Integration**: Task retrieval from Linear issue tracker.
- **Git Worktree Management**: Isolated feature development.
- **PostgreSQL**: Persistent storage for sessions and state.

## Workflow

[![Dark Factory](/media/dark-factory.jpg)](/media/dark-factory.png)

## Quick Start

```bash
# Install dependencies
uv sync --all-extras --dev

# Run migrations, frontend and backend apps
uv run alembic upgrade head
uv run fastapi dev demetra/app.py --host 0.0.0.0 --port 8081
cd react && bun run dev --host

# Add shared env and project via frontend app
# And run the project (auto mode enabled by default)
uv run main.py --project-name <project_name>
```

## Configuration

Set environment variables via `.env` or shell, check [settings.py](demetra/settings.py) for the options.

## Development

```bash
make check         # Type checking + pre-commit
make test          # Run tests
make ci            # Run a full CI pipline
```

See [AGENTS.md](AGENTS.md) and [Wiki](wiki/INDEX.md) for development guidelines and detailed info.
