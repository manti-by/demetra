# Demetra

Demetra is a coding workflow orchestration tool that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

## Features

- **Workflow Orchestration**: Coordinates the entire development lifecycle from task retrieval to code review
- **Linear Integration**: Retrieves and prioritizes tasks from Linear issue tracker
- **OpenCode Integration**: Plans and builds features using OpenCode plan/build agents
- **Cursor Integration**: Reviews code changes with AI-powered feedback
- **CodeRabbit Integration** (Optional): A more powerful alternative to Cursor for code review but more expensive
- **Git Worktree Management**: Isolates feature work using git worktrees
- **Terminal UI**: Rich console output with styled messages and ASCII header

## Architecture

![DAG Diagram](/media/diagram.jpg)

## Workflow

1. **Task Retrieval**: Fetch the highest-priority TODO task from Linear for the target project
2. **Worktree Setup**: Create a git worktree with a feature branch for isolated work
3. **Planning**: Create an implementation plan using OpenCode's plan agent
4. **User Approval**: Wait for user input (approve / reject / comment) before proceeding
5. **Building**: Implement the feature using OpenCode's build agent
6. **Review**: Check the implementation using Cursor
7. **Iteration**: If review finds issues, re-run build with review feedback
8. **Commit & Push**: Commit changes and push the feature branch
9. **Cleanup**: Remove the git worktree

## Requirements

- Python >=3.13.6, <3.14.0
- Linear API key and Team ID
- OpenCode CLI
- Cursor CLI

## Installation

```bash
uv sync --all-extras --dev
```

## Configuration

Configure the following environment variables (via `.env` or shell):

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECTS_PATH` | Path to projects directory | `$HOME/www` |
| `LINEAR_API_KEY` | Linear API key | - |
| `LINEAR_TEAM_ID` | Linear team ID | - |
| `OPENCODE_PATH` | Path to OpenCode binary | `$HOME/.opencode/bin/opencode` |
| `OPENCODE_MODEL` | OpenCode model to use | `opencode/minimax-m2.5-free` |
| `CODERABBIT_PATH` | Path to CodeRabbit binary | `$HOME/.local/bin/coderabbit` |
| `CURSOR_PATH` | Path to Cursor binary | `$HOME/.cursor/bin/cursor` |
| `GIT_PATH` | Path to git binary | `/usr/bin/git` |
| `GIT_WORKTREE_PATH` | Path for git worktrees | `$HOME/.local/demetra/worktrees/` |

`LINEAR_API_URL` is hardcoded to `https://api.linear.app/graphql`.

## Usage

Run Demetra for a specific project:

```bash
uv run main.py --project-name <project_name>
```

Available make commands:

```bash
make run-odin       # Run workflow on 'odin' project
make run-coruscant  # Run workflow on 'coruscant' project
make check          # Run type checking and pre-commit checks
make pip            # Install dependencies
make update         # Upgrade dependencies and pre-commit hooks
make test           # Run tests
make ci             # Shorthand: pip check test
```

## Project Structure

```
demetra/
├── __init__.py
├── models.py                      # LinearIssue dataclass for task state
├── settings.py                    # Settings and configuration
└── services/
    ├── __init__.py
    ├── coderabbit.py              # CodeRabbit review agent integration
    ├── cursor.py                  # Cursor review agent integration
    ├── filesystem.py              # Project filesystem utilities
    ├── git.py                     # Git worktree, commit, and push operations
    ├── graphql.py                 # GraphQL client for Linear API
    ├── linear.py                  # Linear task retrieval and prioritization
    ├── opencode.py                # OpenCode plan/build agents
    ├── tui.py                     # Terminal UI (Rich console) output helpers
    ├── utils.py                   # Async stream utilities
    ├── queries/
    │   └── get_todo_issues.gql    # GraphQL query for Linear issues
    └── tui/
        └── header.txt             # ASCII art header
main.py                            # Entry point and supervisor orchestration
tests/
├── __init__.py
└── test_basic.py
```

## Dependencies

### Core
- `asyncio` - Asynchronous programming
- `aiofiles` - Async file operations
- `aiohttp` - Async HTTP client
- `python-slugify` - Slug generation for branch names
- `rich` - Terminal UI formatting

### Development
- `debugpy` - Python debugger
- `ipython` - Interactive Python
- `ty` - Python type checker
- `pre-commit` - Git hooks
- `uv-bump` - Version bumping
- `pytest` - Testing framework

## CI/CD

This project uses GitHub Actions for continuous integration. The workflow is defined in `.github/workflows/checks.yml` and runs:
- Dependency installation (with `uv sync --locked`)
- Pre-commit hooks on all files
