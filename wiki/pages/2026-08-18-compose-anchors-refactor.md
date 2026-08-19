---
title: Docker Compose shared-anchor refactor
date: 2026-08-18
type: implementation
status: resolved
session_id: "-"
services: [deploy]
branch: master
tickets: []
tags: [docker, compose, refactor]
related: [2026-08-10-docker-compose-deploy.md, 2026-08-17-docker-setup-review.md]
---

# Docker Compose shared-anchor refactor

## TL;DR

Behavior-preserving refactor of `docker-compose.yaml`: the six `mantiby/demetra:latest` services (`migrate`, `api`, `worker`, `watcher`, `listener`, `rq-dashboard`) previously repeated ~20 identical lines each (image, restart, env_file, DB_HOST/REDIS_URL, volumes, `depends_on` gates). The four long-running app services — `api`, `worker`, `watcher`, `listener` — shared the full six-volume mount list and the three-way `depends_on` (migrate + postgres + redis); `migrate` and `rq-dashboard` each carried a lighter subset (code bind only, redis-only `depends_on`). Introduced three YAML anchors — `x-demetra-env`, `x-demetra-base`, `x-demetra-app` — and merged them with `<<:` so each service only declares what is unique to it (`command`, `LOG_PATH`, `ports`, `deploy.replicas`). Net: `docker-compose.yaml` shrunk from 197 to 179 lines. Verified equivalent by diffing `docker compose config` output against the pre-refactor render.

---

## Overview

The [[2026-08-10-docker-compose-deploy]] compose was written long-hand: `api`, `worker`, `watcher`, `listener` each carried an identical `image` / `restart` / `env_file` / six-volume mount list / three-way `depends_on`, and every app service duplicated `DB_HOST: postgres` + `REDIS_URL: redis://redis:6379/1`. That duplication was the *reason* the [[2026-08-17-docker-setup-review]] found findings 6 and 7 (`watcher`/`listener` pointed at the legacy `db` host; `LOG_PATH` values diverged and crashed at import) — a hostname or log path changed in one block but not the others. Anchors make the shared contract explicit in one place.

## Step 1 — Shared anchors

**File:** `docker-compose.yaml:2-28`

Three top-level `x-*` extension keys (ignored by Compose as services) define the shared definitions:

```yaml
x-demetra-env: &demetra-env
  DB_HOST: postgres
  REDIS_URL: redis://redis:6379/1

x-demetra-base: &demetra-base
  image: mantiby/demetra:latest
  restart: unless-stopped
  env_file: .env.docker

x-demetra-app: &demetra-app
  <<: *demetra-base
  volumes:
    - demetra_app_data:/home/demetra/
    - .:/srv/demetra/src/
    - .keys/.ssh:/home/demetra/.ssh
    - .keys/.gnupg:/home/demetra/.gnupg
    - .keys/.gitconfig:/home/demetra/.gitconfig
    - .keys/.git-credentials:/home/demetra/.git-credentials
    - /mnt/data/www/demetra/log/:/var/log/demetra/
  depends_on:
    migrate:
      condition: service_completed_successfully
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

The four long-running app services become one-liners plus overrides:

```yaml
api:
  <<: *demetra-app
  command: ["uvicorn", "demetra.app:app", "--host", "127.0.0.1", "--port", "8001", "--workers", "4"]
  environment:
    <<: *demetra-env
    LOG_PATH: /var/log/demetra/api.log
  ports:
    - "127.0.0.1:8001:8001"
```

`worker` / `watcher` / `listener` differ only in `command` and `LOG_PATH` (plus `deploy.replicas: 4`). `migrate` and `rq-dashboard` merge the lighter `*demetra-base` and only re-declare what differs — `migrate` drops the app volumes and keeps the `./migrations`-free bind of `.:/srv/demetra/src/`; `rq-dashboard` keeps its redis-only `depends_on` and loopback publish. The `LOG_PATH` per-service override uses the same nested `<<:` merge idiom so the two shared env keys are never repeated.

Notes:

- `environment:` (and `volumes:`/`depends_on:` when re-declared) are replaced whole by an explicit key, never deep-merged — hence the nested `<<: *demetra-env` in each service to keep `DB_HOST`/`REDIS_URL` DRY while adding `LOG_PATH`.
- The nested `<<: *demetra-base` inside `x-demetra-app` resolves fine under Compose v5 (go-yaml merge keys). Validated, not assumed.
- The pre-existing working-tree volume reorder (log bind moved after the `.keys/*` mounts) and the `Dockerfile` entrypoint removal are separate, unrelated changes left untouched.
- One intentional behavior delta: `migrate` now also receives `REDIS_URL` (it inherits `*demetra-env`). Alembic never reads Redis, so this is inert.

## Test Results

- `docker compose config -q` passes with a temp `.env.docker` (gitignored; removed after validation).
- Rendered `docker compose config` diffed against the pre-refactor render: only diffs are (a) the pre-existing volume-ordering change and (b) `REDIS_URL` added to `migrate` — every service's `image`, `command`, `environment`, `ports`, `depends_on`, and `deploy.replicas` are otherwise byte-identical.
- Per-service env spot-check: all six app services render `DB_HOST: postgres` + `REDIS_URL: redis://redis:6379/1`; each gets its own `LOG_PATH`.

## Follow-ups

- Working tree is uncommitted on `master` and also carries unrelated Dockerfile / wiki cleanup changes; needs a proper feature branch + PR per the Git Flow rules in AGENTS.md before anything ships.
- Same DRY treatment could be applied to the `.env.docker.example` template and the `Makefile` `docker-*` targets, which still repeat service lists (e.g. `--scale worker=4`, the scoped `up` lists).

## References

- Related: [[2026-08-10-docker-compose-deploy]] (the compose this refactors)
- Related: [[2026-08-17-docker-setup-review]] (review whose findings the DRY contract prevents recurring)
- External: [MNT-164 — Docker compose (Linear)](https://linear.app/mnt/issue/MNT-164)
