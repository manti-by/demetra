# Demetra

Coding workflow orchestration tool (v1.11.0) that coordinates multiple AI agents to automate software development tasks. Integrates Linear (issues), OpenCode (plan/build/resolve/review), Cursor (review), CodeRabbit (review), with automatic linting (Ruff) and testing (pytest).

![DAG Diagram](/media/interface.jpg)

## Features

- **Workflow Orchestration**: Coordinated development from task to review
- **Linear Integration**: Task retrieval from Linear issue tracker via GraphQL
- **OpenCode Integration**: AI-powered planning, building and review
- **Plan Loop**: Automatically resolve plan questions via a dedicated resolve agent before falling back to Linear
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

# Run with plan loop (auto mode): resolve open plan questions via the resolve agent
# instead of posting them to Linear. Requires --auto (enabled by default).
uv run main.py --project-name <project_name> --plan-loop
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
| `MAX_PLAN_ATTEMPTS`           | Max plan loop iterations between plan and resolve agents | `30` |

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
4. If the plan contains open questions:
   - In auto mode, post questions to Linear and move task to Awaiting Input (default)
   - With `--plan-loop`, dispatch questions to the OpenCode resolve agent (new session)
     and re-run the plan agent with the resolved answers. Capped by `MAX_PLAN_ATTEMPTS`.
5. Post plan to Linear for visibility
6. Build feature (OpenCode)
7. Review with OpenCode/Cursor/CodeRabbit
8. Iterate if issues found
9. Lint (Ruff) and test (pytest)
10. Iterate if issues found
11. Commit, push and create a pull request
12. Update Linear task status
13. Cleanup worktree

## Development

```bash
make check          # Type checking + pre-commit
make test          # Run tests
make update        # Upgrade dependencies
```

See [DOCS.md](DOCS.md) for detailed development guidelines.
