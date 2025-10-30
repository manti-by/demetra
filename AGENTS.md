# AGENTS.md

## Project Overview

Chimera is an AI-powered coding workflow orchestration tool that coordinates multiple AI coding agents to automate software development tasks. It acts as a supervisor agent that integrates with Linear (issue tracking), OpenCode (feature planning and building), and CodeRabbit (code review) to create a seamless development workflow.

## Project Structure

- `chimera/settings.py`: Core configuration and environment variables
- `chimera/models/context.py`: Context dataclass for agent state management
- `chimera/services/opencode.py`: OpenCode plan and build agent integrations
- `chimera/services/coderabbit.py`: CodeRabbit review agent integration
- `chimera/services/linear.py`: Linear GraphQL API integration
- `chimera/services/filesystem.py`: Project filesystem utilities
- `chimera/services/graphql.py`: GraphQL client utilities
- `chimera/services/prompt.py`: Prompt template loading
- `chimera/services/prompts/`: System and workflow prompt templates
- `chimera/services/queries/`: GraphQL query templates
- `main.py`: Entry point and supervisor agent orchestration
- `opencode.json`: OpenCode LSP configuration

## Git Workflow

This project adheres strictly to the Git Flow branching model. AI agents must follow these guidelines:

### Main Branch:

- The `master` branch always contains production-ready, stable code.
- Never commit directly to `master`.
- Do not use `git push --force` on the `master` branch.
- Do not merge branches into `master` without explicit approval.

### Feature Branches:

- Create feature branches using the naming convention `<agent-name>/feature/<issue-id>-<descriptive-name>` (e.g., `opencode/feature/CHIMERA-10-add-user-authentication`).
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
uv sync --upgrade --all-extras --dev
uv run pre-commit autoupdate
```

### Makefile Targets

```bash
make run-odin   # Run workflow on 'odin' project
make check      # Run type checking and pre-commit checks
make pip        # Install dependencies
make update     # Upgrade dependencies and pre-commit hooks
make ci         # Shorthand: pip check test
```

### Running Modules

From the project root, after creating a virtualenv and installing dependencies:

```bash
uv run main.py --project-name <project_name>
```

## Language & Environment

- Python 3.13 (see `pyproject.toml`)
- Follow PEP 8 style guidelines, with Ruff enforcing style and linting (120 char line length)
- Use type hints for public functions and complex code paths
- Prefer f-strings over `.format()` or `%`
- Use list/dict/set comprehensions instead of `map`/`filter` where it improves readability
- Prefer `pathlib.Path` over `os.path` for filesystem paths
- Follow PEP 257 for docstrings where docstrings are used
- Prefer EAFP (try/except) over LBYL (if checks) in Python code

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

## Testing Guidelines

- Use `pytest` for tests (currently no test directory, consider adding `tests/`)

## Environment & Configuration

Environment is controlled primarily via `chimera/settings.py` and `.env`:

- `PROJECTS_PATH`: Base path for projects directory
- `LINEAR_API_KEY`: API key for Linear integration
- `LINEAR_API_URL`: Linear GraphQL API URL
- `LINEAR_TEAM_ID`: Linear team ID
- `OPENCODE_PATH`: Path to OpenCode CLI binary
- `CODERABBIT_PATH`: Path to CodeRabbit CLI binary
- `GROQ_API_KEY`: API key for Groq (LLM)
- `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`: LangSmith tracing configuration
- `HUGGINGFACEHUB_API_TOKEN`: HuggingFace API token

## External Dependencies

Chimera coordinates the following external tools:

- **OpenCode**: AI coding assistant for planning and building features
- **CodeRabbit**: AI-powered code review tool
- **Linear**: Issue tracking via GraphQL API
- **Groq**: LLM powering the supervisor agent (Llama 3.1 8B)

## Security Guidelines

- Never commit secrets, passwords, or API tokens
- Configure sensitive values via environment variables
- Run `bandit` periodically or in CI
- Validate any external input before using it in system calls or network operations

## AI Behavior

Response style – concise and minimal:

- Provide minimal, working code without unnecessary explanation
- Omit comments unless essential for understanding
- Skip boilerplate and obvious patterns unless requested
- Use type inference and shorthand syntax where possible
- Focus on the core solution, skip tangential suggestions
- Assume familiarity with language idioms and patterns
- Let code speak for itself through clear naming and structure
- Avoid over-explaining standard patterns and conventions
- Provide just enough context to understand the solution
- Trust the developer to handle obvious cases independently
