---
title: Docker Compose deploy
date: 2026-08-10
type: implementation
status: resolved
session_id: "-"
services: [deploy, configs, runtime, daemons]
branch: feature/mnt-164-docker-compose
tickets: [MNT-164, MNT-40]
tags: [docker, compose, deploy, makefile, watcher, process-manager, daemon]
related: [2026-03-02-process-manager.md, 2026-07-07-project-deploy-script.md, 2026-08-17-docker-setup-review.md, 2026-08-18-compose-anchors-refactor.md]
---

# Docker Compose deploy

## TL;DR

Added a parallel `docker-compose.yaml` path running the full stack (Postgres, Redis, api, 4 workers, watcher, listener, rq-dashboard, one-shot React build) on `mantiby/demetra`. Systemd `make deploy` unchanged. Driven by `make docker-*` + gitignored `.env.docker`; validated against a live daemon.

---

## Overview

MNT-106 shipped `Dockerfile`; MNT-119 added systemd deploy. This mirrors the app layer in compose — same ports (8001, 9181), same 4 workers. Host nginx still proxies to published ports.

## Step 1 — Compose stack

**File:** `docker-compose.yaml` — project `demetra`, volumes `demetra_db_data`, `demetra_redis_data`, `demetra_react_dist`, `demetra_app_data`:

- `db` — `postgres:18-alpine`, `pg_isready` healthcheck, volume on `/var/lib/postgresql` (not `…/data` — 18+ uses pg_ctlcluster subdirs, docker-library/postgres PR 1259).
- `redis` — `redis:7-alpine`, ping healthcheck.
- `migrate` — one-shot `alembic upgrade head` (`${DEMETRA_IMAGE:-mantiby/demetra:latest}`), gated on `db` healthy, `restart: "no"`.
- `api` — `uvicorn --port 8001 --workers 4`, gated on `migrate: service_completed_successfully` + `db`/`redis` healthy, `127.0.0.1:8001` loopback (host nginx sole ingress).
- `worker` — `python -m demetra.worker` with `deploy.replicas: 4` (mirrors `worker@{1..4}.service`), same gates. `docker-up`/`docker-deploy` also pass `--scale worker=4` for Compose <2.20 compat.
- `watcher`/`listener` — `python -m demetra.watcher/listener`, same gates (`init_db` is only `SELECT 1`; poll loops need real tables).
- `rq-dashboard` — `redis://redis:6379/1 --port 9181`, `127.0.0.1:9181` loopback.
- `react-build` — `oven/bun:1` one-shot `bun install && bun run build` on `./react` (rw) with `demetra_react_dist` on `/app/dist`.

Shared: `env_file: .env.docker` + `environment: DB_HOST=db`, `REDIS_URL=redis://redis:6379/1`, `PARENT_HOME=/home/demetra/`, `LOG_PATH=/root/demetra.log`. App services mount `demetra_app_data` on `/root` (persists worktrees, UV venvs, session logs, auth — otherwise `down` destroys state while Postgres keeps dead `local_path`s) and `${HOME}:/home/demetra:ro` (for `copy_auth_from_parent`).

Runtime deviations from plan:
- `LOG_PATH` override: `dictConfig(LOGGING)` at import (`runtime/tui.py:11` via `app.py`/`watcher.py`/`listener.py`); default `/var/log/demetra/demetra.log` has no parent in container → crash. `/root/demetra.log` lands in persisted volume.
- `react-build` `./react` rw: `bun install` needs `node_modules` under a writable parent.
- `migrate` mounts `./migrations:ro`: `.dockerignore` excludes `migrations/versions` from image.
- Strict `depends_on` on `worker`/`watcher`/`listener` prevents crash-loops.
- Loopback publishes for `api`/`rq-dashboard` (no TLS/auth of own; nginx terminates).
- `docker-deploy` uses `make docker-build` prerequisite (no `build:` in compose, so `docker compose build` is no-op); `pull` scoped to `db redis react-build`; `up -d` scoped to long-running services so one-shots don't re-run and wipe `demetra_react_dist`.

## Step 2 — Make targets

**File:** `Makefile` — `docker-up/down/logs/ps/migrate/clean` (`down -v --remove-orphans`) + `docker-deploy`. `docker-deploy` builds, pulls infra, runs `up --abort-on-container-failure migrate react-build` foreground (fail-fast), then `up -d --scale worker=4 api worker watcher listener rq-dashboard` + `ps`. Scoped bring-up avoids re-running one-shots.

## Step 3 — Env wiring

**Files:** `.env.docker.example`, `.env.docker` (gitignored), `.gitignore` — template + operator copy. Existing `.env` not sanitized (out of scope).

## Step 4 — psycopg-binary dependency

**Files:** `pyproject.toml`, `uv.lock` — restored `psycopg-binary==3.3.4` (pure `psycopg` has no libpq in slim image; `alembic` failed `no pq wrapper available`). Systemd path unaffected (host libpq).

## Test Results

- `docker compose --env-file .env.docker config -q` passes; rendered config shows healthchecks, gates, replicas.
- `docker-deploy`/`docker-up` `--scale worker=4` enforces 4 workers on any Compose v2.
- One-shot lifecycle verified against live daemon; loopback `curl` 200s; app-state survives `down/up` via volume; `down/up/clean` idempotent.
- `make test`, `ruff check`, `ty check` pass.

---

## Source — [[2026-03-02-process-manager]]

MNT-40 (2026-03-02): `watcher` polls Linear TODO every 5 min, spawns `main.py` up to `num_cpu−1`, tracks `sessions` `pending→processed/failed`. Compose `watcher`/`worker` are containerized continuation; original shipped systemd units in `configs/`.

## Follow-ups

Host nginx still serves `react/dist` from `/home/manti/www/demetra/react/dist`; bridging `demetra_react_dist` volume is operator step.

## Consistency notes

- (2026-08-19) Refactored onto anchors — see [[2026-08-18-compose-anchors-refactor]]. Changes: `postgres:18`, volumes `demetra_postgres_data` (was `demetra_db_data`), no `demetra_react_dist`, app mount `/home/demetra/`, per-service `/var/log/demetra/<svc>.log` via bind, `migrate` mounts `.:/srv/demetra/src/`, `react-build` `/srv/demetra/src/`, `--host 0.0.0.0` with `8001:8001`/`9181:9181` all-interfaces, nginx `location / → 127.0.0.1:3000`.
- (2026-08-24) `deploy.replicas` removed; 4 workers via `Makefile:103,123` `--scale worker=4`.
- (2026-09-14) `/rq/` 404: `proxy_pass` lacked trailing slash, dashboard serves on `/`. Fixed `rq-dashboard --url-prefix /rq` (`e2509f1`); nginx unchanged.

## References

- Related: [[2026-07-07-project-deploy-script]], [[2026-08-18-compose-anchors-refactor]], [[2026-08-17-docker-setup-review]]
- External: [MNT-164](https://linear.app/mnt/issue/MNT-164)
