# Demetra

Demetra is a coding workflow orchestration tool that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor that integrates with Linear (issue tracking), OpenCode (feature planning and building), and Cursor (code review) to create a seamless development workflow.

![DAG Diagram](/media/interface.jpg)

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

- Python >=3.13.9, <3.14.0
- Linear API key and Team ID
- OpenCode CLI
- Cursor CLI

## Installation

```bash
uv sync --all-extras --dev
```

### Install and setup OpenCode

```bash
curl -fsSL https://opencode.ai/install | bash
source ~/.bashrc
opencode auth login
```

### Install and setup Cursor CLI

```bash
curl https://cursor.com/install -fsS | bash
agent login
```

### Install and setup CodeRabbit CLI

```bash
curl -fsSL https://cli.coderabbit.ai/install.sh | sh
source ~/.bashrc
coderabbit auth login
```

### Install and setup GitHub CLI

Follow installation instructions [here](https://github.com/cli/cli?tab=readme-ov-file#installation) then login:

```bash
gh auth login
```

### GitHub OAuth Setup

To enable GitHub login for the API, you need to create a GitHub OAuth App:

1. Go to GitHub Settings > Developer settings > OAuth Apps > New OAuth App
2. Fill in the details:
   - Application name: Demetra
   - Homepage URL: `https://demetra.manti.by`
   - Authorization callback URL: `https://demetra.manti.by/api/v1/github/callback`
3. Copy the Client ID and generate a Client Secret
4. Set the following environment variables:

```bash
export GITHUB_CLIENT_ID="your_client_id"
export GITHUB_CLIENT_SECRET="your_client_secret"
export GITHUB_REDIRECT_URI="https://demetra.manti.by/api/v1/github/callback"
export JWT_SECRET_KEY="your_secure_random_key"
```

The JWT secret key should be a secure random string (at least 32 characters).

### Install BUN for React app

```bash
curl -fsSL https://bun.com/install | bash
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
| `DB_PATH` | Path to SQLite database | `$HOME/.demetra/demetra.sqlite3` |
| `CODERABBIT_PATH` | Path to CodeRabbit binary | `$HOME/.local/bin/coderabbit` |
| `CURSOR_PATH` | Path to Cursor binary | `$HOME/.local/bin/cursor-agent` |
| `GIT_PATH` | Path to git binary | `/usr/bin/git` |
| `GIT_WORKTREE_PATH` | Path for git worktrees | `$HOME/.demetra/worktrees/` |
| `LINEAR_STATE_TODO_ID` | Linear TODO state ID | *(project-specific)* |
| `LINEAR_STATE_IN_PROGRESS_ID` | Linear In Progress state ID | *(project-specific)* |
| `LINEAR_STATE_IN_REVIEW_ID` | Linear In Review state ID | *(project-specific)* |
| `GITHUB_CLIENT_ID` | GitHub OAuth App client ID | - |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth App client secret | - |
| `GITHUB_REDIRECT_URI` | GitHub OAuth callback URL | `https://demetra.manti.by/api/v1/github/callback` |
| `JWT_SECRET_KEY` | Secret key for JWT token signing | - |

`LINEAR_API_URL` is hardcoded to `https://api.linear.app/graphql`.

## Usage

Run Demetra for a specific project:

```bash
uv run main.py --project-name <project_name>
```

Available make commands:

```bash
make run-chimera     # Run workflow on 'chimera' project
make run-demetra     # Run workflow on 'demetra' project
make run-odin        # Run workflow on 'odin' project
make run-coruscant   # Run workflow on 'coruscant' project
make check           # Run type checking and pre-commit checks
make pip             # Install dependencies
make update          # Upgrade dependencies and pre-commit hooks
make test            # Run tests
make ci              # Shorthand: pip check test
make react-install   # Install React app dependencies
make react-build     # Build React app
make react-dev       # Run React app in development mode
make react-test      # Run React app tests
```

## Project Structure

```
demetra/
├── __init__.py
├── exceptions.py                  # Custom exception classes
├── models.py                      # LinearIssue dataclass for task state
├── settings.py                    # Settings and configuration
└── services/
    ├── __init__.py
    ├── coderabbit.py              # CodeRabbit review agent integration
    ├── cursor.py                  # Cursor review agent integration
    ├── database.py                # SQLite database operations
    ├── filesystem.py              # Project filesystem utilities
    ├── flow.py                    # Workflow orchestration logic
    ├── git.py                     # Git worktree, commit, and push operations
    ├── graphql.py                 # GraphQL client for Linear API
    ├── linear.py                  # Linear task retrieval and prioritization
    ├── lint.py                    # Code linting operations
    ├── opencode.py                # OpenCode plan/build agents
    ├── subprocess.py              # Subprocess execution utilities
    ├── test.py                    # Test runner utilities
    ├── tui.py                     # Terminal UI (Rich console) output helpers
    ├── utils.py                   # Async stream utilities
    ├── queries/
    │   ├── get_todo_issues.gql    # GraphQL query for Linear issues
    │   ├── list_states.gql        # GraphQL query for Linear states
    │   └── update_issue_status.gql # GraphQL mutation for issue status
    └── tui/
        └── header.txt             # ASCII art header
main.py                            # Entry point and supervisor orchestration
tests/                             # Comprehensive test suite
```

## Dependencies

### Core
- `asyncio` - Asynchronous programming
- `aiofiles` - Async file operations
- `aiohttp` - Async HTTP client
- `psycopg` - Async PostgreSQL database
- `python-slugify` - Slug generation for branch names
- `rich` - Terminal UI formatting
- `langchain-groq` - LLM integration with Groq
- `langchain-core` - LangChain core library

### Development
- `debugpy` - Python debugger
- `ipython` - Interactive Python
- `ty` - Python type checker
- `pre-commit` - Git hooks
- `uv-bump` - Version bumping
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support

## Git Workflow

This project adheres strictly to the Git Flow branching model:

### Main Branch
- The `master` branch always contains production-ready, stable code.
- Never commit directly to `master`.
- Do not use `git push --force` on the `master` branch.
- Do not merge branches into `master` without explicit approval.

### Feature Branches
- Create feature branches using the naming convention `<agent-name>/feature/<issue-id>-<descriptive-name>`.
- Use the [Conventional Commits](https://www.conventionalcommits.org) specification for commit messages.
- Ensure all local tests pass before committing.

### Pull Requests
- Open a Pull Request for every completed feature branch.
- PRs must be reviewed and pass all CI checks before merging.

## Linear Workflow

- When starting implementation of any issue from `TODO`, move it to `In Progress` column.
- When feature is completed and PR is created, move it to `In Review` column.
- After approval, merge the feature branch into `master` and move the issue to `Done` column.
- If the feature branch is not merged into `master`, move it back to `In Progress` column.
- If the feature branch is closed without merging, move it to `Closed` column.

## Security Guidelines

- Never commit secrets, passwords, or API tokens
- Configure sensitive values via environment variables
- Run `bandit` periodically or in CI
- Validate any external input before using it in system calls or network operations

## AI Behavior

Response style -- concise and minimal:
- Provide minimal, working code without unnecessary explanation
- Omit comments unless essential for understanding
- Skip boilerplate and obvious patterns unless requested
- Use type inference and shorthand syntax where possible
- Focus on the core solution, skip tangential suggestions

## CI/CD

This project uses GitHub Actions for continuous integration. The workflow is defined in `.github/workflows/checks.yml` and runs:
- Dependency installation (with `uv sync --locked`)
- Pre-commit hooks on all files
