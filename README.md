# Demetra

Coding workflow orchestration tool (v1.8.4) that coordinates multiple AI agents to automate software development tasks. Integrates Linear (issues), OpenCode (plan/build/review), Cursor (review), CodeRabbit (review), with automatic linting (Ruff) and testing (pytest).

![DAG Diagram](/media/interface.jpg)

## Features

- **Workflow Orchestration**: Coordinated development from task to review
- **Linear Integration**: Task retrieval from Linear issue tracker via GraphQL
- **OpenCode Integration**: AI-powered planning, building and review
- **Cursor Integration**: Alternative AI code review
- **CodeRabbit Integration**: Alternative AI code review
- **Git Worktree Management**: Isolated feature development
- **PostgreSQL + SQLite**: Persistent storage for sessions and state

## Quick Start

```bash
# Install dependencies
uv sync --all-extras --dev

# Run for a project (auto mode enabled by default)
uv run main.py --project-name <project_name>

# Run with manual mode (prompts for approval)
uv run main.py --project-name <project_name> --auto=false

# Run specific Linear task
uv run main.py --project-name <project_name> --task-id <task_id>
```

## Configuration

Set environment variables via `.env` or shell:

| Variable | Description | Default |
|-------------------------------|--------------------|-------------|
| `PROJECTS_PATH`               | Projects directory | `$HOME/www` |
| `LINEAR_API_KEY`              | Linear API key     | -           |
| `LINEAR_API_URL`              | Linear GraphQL URL | `https://api.linear.app/graphql` |
| `LINEAR_TEAM_ID`              | Linear team ID     | -           |
| `LINEAR_STATE_TODO_ID`        | TODO state ID      | -           |
| `LINEAR_STATE_IN_PROGRESS_ID` | In Progress state  | -           |
| `LINEAR_STATE_IN_REVIEW_ID`   | In Review state    | -           |

### CLI Paths

| Variable                      | Default                          |
|-------------------------------|----------------------------------|
| `OPENCODE_PATH`               | `$HOME/.opencode/bin/opencode`   |
| `OPENCODE_MODEL`              | `opencode/minimax-m2.5-free`     |
| `CURSOR_PATH`                 | `$HOME/.local/bin/cursor-agent`  |
| `CODERABBIT_PATH`             | `$HOME/.local/bin/coderabbit`    |
| `DB_PATH`                     | `$HOME/.demetra/demetra.sqlite3` |
| `GIT_WORKTREE_PATH`           | `$HOME/.demetra/worktrees/`     |

## Workflow

1. Fetch highest-priority TODO task from Linear
2. Create git worktree with feature branch
3. Generate implementation plan (OpenCode)
4. Post plan to Linear for visibility
5. Build feature (OpenCode)
6. Review with OpenCode/Cursor/CodeRabbit
7. Iterate if issues found
8. Lint (Ruff) and test (pytest)
9. Iterate if issues found
10. Commit, push and create a pull request
11. Update Linear task status
12. Cleanup worktree

## Development

```bash
make check          # Type checking + pre-commit
make test          # Run tests
make update        # Upgrade dependencies
```

See [DOCS.md](DOCS.md) for detailed development guidelines.
