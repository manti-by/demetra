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
related:
- 2026-08-17-docker-setup-review.md
- 2026-08-10-docker-compose-deploy.md
---

# Docker Compose shared-anchor refactor

## TL;DR

DRY refactor of `docker-compose.yaml`: six `mantiby/demetra:latest` services repeated ~20 identical lines; introduced three YAML anchors (`x-demetra-env`, `x-demetra-base`, `x-demetra-app`) merged via `<<:` so each service declares only `command`/`LOG_PATH`/`ports`/`replicas`. 197→179 lines; verified by diffing `docker compose config` output.

---

## Overview

Long-hand compose caused [[2026-08-17-docker-setup-review]] findings 6–7 (`watcher`/`listener` stale `db` host, divergent `LOG_PATH` crashes). Anchors make the shared contract single-source.

## Step 1 — Shared anchors

**File:** `docker-compose.yaml:2-28`

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
    migrate: { condition: service_completed_successfully }
    postgres: { condition: service_healthy }
    redis: { condition: service_healthy }
```

App services become one-liners:

```yaml
api:
  <<: *demetra-app
  command: ["uvicorn", "demetra.app:app", "--host", "127.0.0.1", "--port", "8001", "--workers", "4"]
  environment: { <<: *demetra-env, LOG_PATH: /var/log/demetra/api.log }
  ports: ["127.0.0.1:8001:8001"]
```

`worker`/`watcher`/`listener` differ only in `command`/`LOG_PATH` (plus `deploy.replicas: 4`). `migrate`/`rq-dashboard` merge the lighter `*demetra-base` with their own volumes/`depends_on`. Notes:

- `environment:`/`volumes:`/`depends_on:` are replaced, not deep-merged — hence nested `<<: *demetra-env`.
- Nested `<<: *demetra-base` inside `x-demetra-app` resolves under Compose v5 (go-yaml).
- One intentional delta: `migrate` now also gets `REDIS_URL` (inert; alembic doesn't read Redis).

## Test Results

- `docker compose config -q` passes.
- Rendered `config` diff vs pre-refactor: only (a) pre-existing volume order and (b) `REDIS_URL` on `migrate` differ; all `image`/`command`/`environment`/`ports`/`depends_on`/`replicas` identical.
- Spot-check: all six app services render `DB_HOST: postgres` + `REDIS_URL`; each own `LOG_PATH`.

## Consistency note (2026-08-23)

At refactor time `api` used `--host 127.0.0.1` + loopback publish; current `master` uses `--host 0.0.0.0` + all-interface `8001:8001`/`9181:9181` (see [[2026-08-17-docker-setup-review]] #12).

## Follow-ups

- Landed on `master` (live).
- Same DRY could apply to `.env.docker.example` and `Makefile` service lists.

> **Consistency note (2026-08-24):** `deploy.replicas` removed; workers via `Makefile` `--scale worker=4`.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-10-docker-compose-deploy]], [[2026-08-17-docker-setup-review]]
- External: [MNT-164](https://linear.app/mnt/issue/MNT-164)
