---
title: Docker Compose deploy
date: 2026-08-10
type: implementation
status: resolved
session_id: -
services: [deploy, configs]
branch: feature/mnt-164-docker-compose
tickets: [MNT-164]
tags: [docker, compose, deploy, makefile]
related: [2026-07-07-project-deploy-script.md]
---

# Docker Compose deploy

## TL;DR

Added a parallel `docker-compose.yaml` deployment path that runs the full app layer (Postgres, Redis, api, worker x4, watcher, listener, rq-dashboard, one-shot React build) on top of the `mantiby/demetra` image. The systemd `make deploy` path from MNT-119 stays untouched; compose is a second production path driven by new `make docker-*` targets and a gitignored `.env.docker`. Validated end to end against a live Docker daemon, which surfaced several runtime fixes beyond the original plan (postgres 18 mount path, LOG_PATH crash, one-shot deploy sequencing, rq-dashboard flags/exposure, app-state persistence, and a missing `psycopg-binary` dependency).

---

## Overview

MNT-106 shipped a single-image `Dockerfile`; MNT-119 added the systemd deploy path (`configs/services/*.service`, host nginx). This ticket mirrors the same app layer in compose so the stack can run without systemd — same commands, same ports (api `8001`, rq-dashboard `9181`), same 4 workers. Nginx stays on the host and keeps proxying to the same published ports.

## Step 1 — Compose stack

**File:** `docker-compose.yaml`

Services on the default network, project name `demetra`, four explicitly-named volumes (`demetra_db_data`, `demetra_redis_data`, `demetra_react_dist`, `demetra_app_data`):

- `db` — `postgres:18-alpine`, `pg_isready` healthcheck. Volume on `/var/lib/postgresql`, **not** `/var/lib/postgresql/data`: the 18+ images moved to pg_ctlcluster-style major-version subdirectories (docker-library/postgres PR 1259) and refuse to boot with a `data`-only mount.
- `redis` — `redis:7-alpine`, `redis-cli ping` healthcheck, volume on `/data`.
- `migrate` — one-shot `alembic upgrade head` from the `${DEMETRA_IMAGE:-mantiby/demetra:latest}` image, gated on `db` healthy, `restart: "no"`.
- `api` — `uvicorn demetra.app:app --port 8001 --workers 4`, gated on `migrate: service_completed_successfully` + `db`/`redis` healthy, publishes `127.0.0.1:8001` (host loopback only — host nginx `/api/`/`/ws/` proxies to `127.0.0.1:8001` are the sole ingress, mirroring the systemd `api.service` uvicorn default `127.0.0.1` bind).
- `worker` — `python -m demetra.worker` with `deploy.replicas: 4` (mirrors `worker@{1..4}.service`), gated on `migrate: service_completed_successfully` + `db`/`redis` healthy — RQ jobs touch the schema, so workers must not start before migrations run. Note: `docker compose up` only honours `deploy.replicas` from Compose v2.20; the `docker-up`/`docker-deploy` targets pass `--scale worker=4` so the four workers run on any Compose v2.
- `watcher` / `listener` — `python -m demetra.watcher` / `python -m demetra.listener`, gated on `migrate: service_completed_successfully` + `db`/`redis` healthy (their poll loops hit real tables; `init_db()` itself is only a `SELECT 1` connectivity check).
- `rq-dashboard` — `rq-dashboard --redis-url redis://redis:6379/1 --port 9181`, published on host loopback only (`127.0.0.1:9181`), gated on `redis` healthy.
- `react-build` — one-shot `oven/bun:1` running `bun install --frozen-lockfile && bun run build` against `./react` (mounted read-write) with `demetra_react_dist` on `/app/dist`.

App services share `env_file: .env.docker` plus fixed `environment:` overrides: `DB_HOST=db`, `REDIS_URL=redis://redis:6379/1`, `PARENT_HOME=/home/demetra/`, `LOG_PATH=/root/demetra.log`. The four app services (`api`, `worker`, `watcher`, `listener`) mount two extra volumes: `demetra_app_data` on `/root` (persists worktrees, projects, per-project UV venvs from MNT-161, session logs, copied auth — otherwise every `docker down`+`up` or image update destroys the app state while Postgres keeps rows pointing at dead `local_path`s) and `${HOME}:/home/demetra:ro` (the parent home that `copy_auth_from_parent` reads — without it, `PARENT_HOME.is_dir()` fails and auth copying silently no-ops; this mirrors the existing `docker-run` target's `-v "$(HOME):/home/manti/:ro"`).

Runtime-proven deviations from the plan (each verified against a live daemon):

- `LOG_PATH` override on the app services. The app runs `logging.config.dictConfig(LOGGING)` at module import (`demetra/services/runtime/tui.py:11`, reached from `app.py` via `services/auth/__init__.py`, and at `watcher.py:10` / `listener.py:19`), and the default `LOG_PATH` (`/var/log/demetra/demetra.log`) has no writable parent directory in the containers — the import crashes (`ValueError: Unable to configure handler 'file'`). `/root/demetra.log` lands in the persisted `demetra_app_data` volume, so session logs (`LOG_DIR/sessions`) survive restarts too.
- `react-build` mounts `./react` read-write. With a read-only source, `bun install` has nowhere to write `node_modules` (Docker cannot create the mountpoint under a read-only parent — `mkdirat .../app/node_modules: read-only file system`). A writable mount mirrors the systemd deploy exactly (`cd react && bun install`), and `node_modules` is already gitignored.
- `migrate` bind-mounts `./migrations:/app/migrations:ro`. Reason: `.dockerignore:29` excludes `migrations/versions` from the image build context, so the migration files are not inside `mantiby/demetra`; without the mount, `alembic upgrade head` finds no revisions.
- The health/migrate-gated `depends_on` on `worker`/`watcher`/`listener` (not just `api`) prevents startup crash-loops.
- `api` publishes on `127.0.0.1:8001` (loopback) instead of `0.0.0.0:8001` — the API surface (`/docs`, webhook receivers, `/users/me/env` CRUD) has no TLS of its own, so it must not be reachable outside the host; nginx terminates TLS and proxies to `127.0.0.1:8001`, the same ingress topology as the systemd `api.service` (uvicorn's default `127.0.0.1` bind).
- `rq-dashboard` publishes on `127.0.0.1:9181` (loopback) instead of `0.0.0.0:9181` — the dashboard has no auth and lets anyone browse/cancel jobs, so it is reachable only through the host nginx `/rq/` proxy (which proxies to `127.0.0.1:9181`), matching the systemd topology. The `--bind 0.0.0.0` and `--host` flags are dropped: `rq-dashboard` 0.9.0 has no `--host` option at all, and the image's default bind is used.
- `docker-deploy` builds the image through the existing `make docker-build` target (a Makefile prerequisite) rather than `docker compose build` — the compose services have no `build:` sections, so `docker compose build` is a silent no-op ("No services to build") that would deploy whatever `mantiby/demetra:latest` resolves to. The compose `pull` step is scoped to `db redis react-build` so it does not clobber the freshly built app image, and both `docker-up` and the `docker-deploy` detached phase scope `up -d` to the long-running services so the `migrate`/`react-build` one-shots never run twice.
- `db` volume mounts on `/var/lib/postgresql`, **not** `/var/lib/postgresql/data`: the 18+ images moved to pg_ctlcluster-style major-version subdirectories (docker-library/postgres PR 1259) and refuse to boot with a `data`-only mount.

## Step 2 — Make targets

**File:** `Makefile`

New targets beside the existing `docker-build`/`deploy` targets, all passing `--env-file .env.docker` and assuming Compose v2: `docker-up`, `docker-down`, `docker-logs`, `docker-ps`, `docker-migrate`, `docker-clean` (`down -v --remove-orphans`, destroys volumes), and `docker-deploy`. The systemd `deploy` target is untouched.

`docker-deploy` depends on the existing `make docker-build` target (so local code is actually built — `docker compose build` alone would be a no-op since the services only declare `image:`), then pulls the infra images, runs the one-shot services in the foreground first — `docker compose up --abort-on-container-failure migrate react-build` — so migrations and the frontend build complete (and a non-zero exit fails the target) before the long-running services start. The detached bring-up is scoped to the long-running services only — `docker compose up -d --scale worker=4 api worker watcher listener rq-dashboard` — because compose `up` re-creates any stopped service: an unscoped `up -d` would re-run the just-completed one-shots, and a second `react-build` wipes `demetra_react_dist` (Vite empties `outDir`) before rebuilding in the background — a failed background rebuild would leave the frontend broken while the deploy still exits 0. The scoped services' `depends_on: migrate: condition: service_completed_successfully` is satisfied by the already-exited migrate container, and `react-build` (a dependency of nothing) is skipped. `docker-up` uses the same scoped bring-up — it is a restart command for the long-running stack, so the one-shots never re-run (schema and dist persist in the named volumes across down/up; `docker-deploy` owns the one-shot/build phase). A trailing `docker compose ps` in `docker-deploy` then shows the final state. Both `docker-up` and `docker-deploy` pass `--scale worker=4` because `deploy.replicas` is only honoured by `docker compose up` from Compose v2.20 — the explicit scale keeps the four workers on any Compose v2.

## Step 3 — Env wiring

**File:** `.env.docker.example`, `.env.docker` (gitignored), `.gitignore`

`.env.docker.example` is the sanitized template (postgres/app DB creds, secrets, GitHub/Linear/Groq keys, daemon intervals, `LOG_PATH`). The operator copies it to `.env.docker` and fills in real values; `.gitignore` gained a `.env.docker` entry (`.dockerignore` already covers `.env.*`, so the file never reaches the image either way). The existing committed `.env` was not sanitized — out of scope for MNT-164.

## Step 4 — psycopg-binary dependency

**File:** `pyproject.toml`, `uv.lock`

Running `migrate` inside the image exposed a latent packaging bug: `psycopg==3.3.4` is declared pure, and the slim base image has neither `psycopg-binary` nor system libpq, so `alembic upgrade head` died with `ImportError: no pq wrapper available`. The systemd path never hit this — it runs alembic on the host, where brew libpq satisfies psycopg. `psycopg-binary==3.3.4` (removed in an earlier "Review updates" commit) was restored to the dependencies; it is inert on the host and bundles libpq in the image. No `Dockerfile` change was needed — the image's `uv sync` picks it up.

## Test Results

- `docker compose --env-file .env.docker config -q` passes; rendered config shows the healthchecks, the `service_completed_successfully` gates on `api`/`worker`/`watcher`/`listener`, and `deploy.replicas: 4` on `worker`.
- `docker-up`/`docker-deploy` pass `--scale worker=4`, so the four workers are enforced even on Compose v2 < 2.20 where `deploy.replicas` is silently ignored by `docker compose up`.
- One-shot lifecycle verified against a live daemon: `up -d` returns immediately (one-shots still running), `wait` propagates exit codes but errors when a one-shot already exited, and foreground `up --abort-on-container-failure` blocks, re-runs exited one-shots, and exits non-zero on failure — the pattern `docker-deploy` uses.
- `make docker-deploy` brings the stack up (image built via the `docker-build` prerequisite); `docker compose ps` shows every service `Up` with `migrate` and `react-build` exited 0.
- `curl -fsS http://localhost:8001/docs` returns 200 (FastAPI docs) and `curl -fsS http://localhost:9181` serves the RQ dashboard, both from the host loopback; the publishes are `127.0.0.1`-only so nothing is exposed to the network.
- App-state persistence: a marker written to `/root` inside the api container survives `make docker-down` + `make docker-up` (container recreate) via the `demetra_app_data` volume.
- `make docker-down` / `docker-up` idempotent; `docker-clean` removes the four named volumes.
- `make test`, `uv run ruff check .`, `uv run ty check` pass (only change to Python surface: the added `psycopg-binary` dependency).

---

## Follow-ups

- Host nginx still serves `react/dist` from `/home/manti/www/demetra/react/dist`; bridging the compose `demetra_react_dist` volume to that path (bind-mount or copy) is an operator step, not automated.

## References

- Related: [[2026-07-07-project-deploy-script]]
- External: [MNT-164 — Docker compose (Linear)](https://linear.app/mnt/issue/MNT-164)
