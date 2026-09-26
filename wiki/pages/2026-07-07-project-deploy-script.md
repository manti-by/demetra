---
title: Project deploy script
date: 2026-07-07
type: implementation
status: resolved
session_id: "-"
services: [deploy, configs]
branch: "-"
tickets: [MNT-119]
tags: [deploy, setup, systemd, makefile]
related:
- 2026-08-10-docker-compose-deploy.md
---

# Project deploy script

## TL;DR

Added a fast deploy path: `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, with systemd units and nginx. Auth (GitHub/OpenCode) lives in `.env` via `EnvironmentFile`. Docker (MNT-106) remains an alternative.

---

## Overview

Manual deploys were slow; wiring GitHub + OpenCode auth on a fresh host was the main pain point.

## Changes

- **Makefile `deploy`**: `git pull --ff-only` → `uv sync` → `alembic upgrade head` → `bun install` + `bun run build` in `react` → `daemon-reload` + restart `demetra-api`, `react`, `watcher`, `listener`, `worker@1..4` → nginx reload.
- **Bootstrap** (`configs/bootstrap.sh`): symlinks, enables, and starts systemd services (`configs/services/*.service`) and nginx site (`configs/nginx.conf`).
- **Auth**: credentials in `.env` consumed via systemd `EnvironmentFile` — no interactive prompts.
- **Docker**: alternative path via MNT-106 compose stack (`mantiby/demetra`), documented in [[2026-08-10-docker-compose-deploy]].

## Test Results

Bootstrap verified on fresh host; `deploy` target exercised end-to-end.

---

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: none
- External: [MNT-119 — Project deploy script (Linear)](https://linear.app/mnt/issue/MNT-119)
