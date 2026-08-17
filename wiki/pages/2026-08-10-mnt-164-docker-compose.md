---
title: 'MNT-164: Docker compose'
date: '2026-08-10'
type: implementation
status: resolved
session_id: ses_013d53a7fffeEP8eYmZpldT5PW
services: []
branch: mnt-164-docker-compose
tickets: [MNT-164]
tags: [wiki, backend, feature]
related: []
---
# MNT-164: Docker compose

## TL;DR

Implementation session for MNT-164: Docker compose on branch `mnt-164-docker-compose`.

---

## Overview

Changed 0 file(s) (0 lines) affecting services: none. Primary files: none.

## Changed files

- No changed files captured.

## Stat

```text
- no stat
```

## Build plan

## Implementation Plan
### Approach
Add a parallel `docker-compose.yaml` deployment path that mirrors the existing systemd layout (Postgres + Redis + api/worker×4/watcher/listener/rq-dashboard + React build) on top of the published `mantiby/demetra` image.

### Build Steps
1. **Create `docker-compose.yaml`** at the repo root with services:
   * `db`: `postgres:18-alpine`, healthcheck `pg_isready`, env from `.env.docker`, volume `demetra_db_data:/var/lib/postgresql/data`.
   * `redis`: `redis:7-alpine`, healthcheck `redis-cli ping`, volume `demetra_redis_data:/data`.
   * `migrate`: image `${DEMETRA_IMAGE:-mantiby/demetra:latest}`, `command: alembic upgrade head`, `depends_on: db: condition: service_healthy`, `env_file: .env.docker`.
   * `api`: same image, `command: uvicorn demetra.app:app…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_013d53a7fffeEP8eYmZpldT5PW`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-164/docker-compose
