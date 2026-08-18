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

# Run for a project (auto mode enabled by default)
uv run main.py --project-name <project_name>
```

## Configuration

Set environment variables via `.env` or shell, check [settings.py](demetra/settings.py) for the options.

## Docker Compose

Alternative deployment path that runs the full app layer (Postgres, Redis, API, 4 workers, watcher, listener, RQ dashboard and a one-shot React build) on top of the `mantiby/demetra` image. The systemd `make deploy` path is untouched.

Prerequisites: Docker Compose v2 (the compose file declares `deploy.replicas: 4` for the workers — honoured by `docker compose up` from v2.20; the `docker-up`/`docker-deploy` targets pass `--scale worker=4` so 4 workers run on any v2), the `mantiby/demetra:latest` image (built from the local Dockerfile by `make docker-build`, which `docker-deploy` runs as a prerequisite; the `db`/`redis`/`oven/bun` images are pulled automatically), and `docker-build` needs Docker BuildKit.

```bash
cp .env.docker.example .env.docker   # then fill in real values
make docker-deploy                   # build image + pull infra + migrate/react one-shots + up long-running + ps
```

Port map: API on `http://localhost:8001` (published on host loopback only — host nginx `/api/` and `/ws/` proxies to `127.0.0.1:8001` are the only ingress, matching the systemd `api.service` uvicorn default bind). The RQ dashboard is also loopback-only (`127.0.0.1:9181`) via the host nginx `/rq/` proxy.

`make docker-up` brings up the long-running services only — the `migrate`/`react-build` one-shots run as part of `make docker-deploy` (foreground, failure-fatal). The React build writes to `./react/dist` on the host (where nginx serves the frontend). App state (worktrees, projects) persists in the `demetra_app_data` volume on `/home/demetra`; git/SSH/GPG credentials are bind-mounted from `.keys/`. Container logs land in `./log` by default (`DEMETRA_LOG_DIR` overrides on production). See `make docker-up`, `docker-down`, `docker-logs`, `docker-ps`, `docker-migrate`, `docker-clean` for the remaining lifecycle commands.

## Development

```bash
make check         # Type checking + pre-commit
make test          # Run tests
make ci            # Run a full CI pipline
```

See [AGENTS.md](AGENTS.md) and [Wiki](wiki/INDEX.md) for development guidelines and detailed info.
