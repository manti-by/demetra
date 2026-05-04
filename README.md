# Demetra

Coding workflow orchestration tool that coordinates multiple AI agents to automate software development tasks. Integrates Linear (issues), OpenCode (plan/build), and Cursor (review).

## Features

- **Workflow Orchestration**: Coordinated development from task to review
- **Linear Integration**: Task retrieval from Linear issue tracker
- **OpenCode Integration**: AI-powered planning and building
- **Cursor Integration**: AI code review with feedback
- **Git Worktree Management**: Isolated feature development

## Quick Start

```bash
# Install dependencies
uv sync --all-extras --dev

# Run for a project
uv run main.py --project-name <project_name>
```

Or use Makefile:

```bash
make run-chimera     # Run on 'chimera'
make run-demetra     # Run on 'demetra'
make run-odin       # Run on 'odin'
```

## Configuration

Set environment variables via `.env` or shell:

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECTS_PATH` | Projects directory | `$HOME/www` |
| `LINEAR_API_KEY` | Linear API key | - |
| `LINEAR_TEAM_ID` | Linear team ID | - |
| `LINEAR_STATE_TODO_ID` | TODO state ID | - |
| `LINEAR_STATE_IN_PROGRESS_ID` | In Progress state | - |
| `LINEAR_STATE_IN_REVIEW_ID` | In Review state | - |

### CLI Paths

| Variable | Default |
|----------|---------|
| `OPENCODE_PATH` | `$HOME/.opencode/bin/opencode` |
| `OPENCODE_MODEL` | `opencode/minimax-m2.5-free` |
| `CURSOR_PATH` | `$HOME/.local/bin/cursor-agent` |
| `CODERABBIT_PATH` | `$HOME/.local/bin/coderabbit` |
| `DB_PATH` | `$HOME/.demetra/demetra.sqlite3` |

## Workflow

1. Fetch highest-priority TODO task from Linear
2. Create git worktree with feature branch
3. Generate implementation plan (OpenCode)
4. Wait for user approval
5. Build feature (OpenCode)
6. Review with Cursor
7. Iterate if issues found
8. Commit & push
9. Cleanup worktree

## Development

```bash
make check          # Type checking + pre-commit
make test          # Run tests
make update        # Upgrade dependencies
```

See [AGENTS.md](AGENTS.md) for detailed development guidelines.