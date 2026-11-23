---
title: Project deploy script
generated: {by: demetra, at: '2026-07-07T00:00:00Z'}
description: Records MNT-119 introducing a fast manual deploy path with a `Makefile` `deploy` target, `configs/bootstrap.sh`, systemd units and nginx; archived into the Docker Compose deploy page because the systemd path was removed in `f5904d5` and `make deploy` now drives the Docker Compose stack.
type: implementation
status: deprecated
session_id: '-'
services: [deploy, configs]
branch: '-'
tickets: [MNT-119]
tags: [deploy, setup, systemd, makefile]
related: [2026-08-10-docker-compose-deploy.md]
---

# Project deploy script

> **Archived on 2026-11-15.** Useful info merged into
> [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md). See wiki/archive/ for the original.

## TL;DR

Added a fast deploy path: `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, with systemd units and nginx. Auth (GitHub/OpenCode) lives in `.env` via `EnvironmentFile`. Docker (MNT-106) remains an alternative.

---

## Overview

Manual deploys were slow; wiring GitHub + OpenCode auth on a fresh host was the main pain point.

## Changes

- **Makefile `deploy`**: `git pull --ff-only` → `uv sync` → `alembic upgrade head` → `bun install` + `bun run build` in `react` → `daemon-reload` + restart `demetra-api`, `react`, `watcher`, `listener`, `worker@1..4` → nginx reload.
- **Bootstrap** (`configs/bootstrap.sh`): symlinks, enables, and starts systemd services (`configs/services/*.service`) and nginx site (`configs/nginx.conf`).
- **Auth**: credentials in `.env` consumed via systemd `EnvironmentFile` — no interactive prompts.
- **Docker**: alternative path via MNT-106 compose stack (`mantiby/demetra`), documented in [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md).

## Test Results

Bootstrap verified on fresh host; `deploy` target exercised end-to-end.

---

## Follow-ups

None.

> **Status (2026-10-26, Consistency Agent):** Superseded. The systemd path described above (`configs/bootstrap.sh`, `configs/services/*.service`, `systemctl restart demetra-*`) was removed in `f5904d5` (2026-09-11); `make deploy` now runs the Docker Compose stack (Postgres, Redis, API, workers, watcher, listener, RQ dashboard and a one-shot React build). See [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md).

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md)
- External: [MNT-119 — Project deploy script (Linear)](https://linear.app/mnt/issue/MNT-119)

> **Consistency note (2026-11-11, Consistency Agent):** This page documents the **retired** systemd deploy path. `configs/bootstrap.sh` and `configs/services/*.service` were deleted in `f5904d5` (2026-09-11); `configs/` now holds only `docker-entrypoint.sh`, `nginx.conf` and `proxy.params`. The current path is `make deploy` (Docker compose, `Makefile:26-33`): `git pull` → `docker build` → `docker compose pull` → one-shot `migrate`/`react-build` → `docker compose up --scale worker=2` → `sudo service nginx reload`. Treat the body above as history.
