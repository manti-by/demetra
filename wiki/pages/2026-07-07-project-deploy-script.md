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
related: [2026-08-10-docker-compose-deploy.md]
---

# Project deploy script

## TL;DR

Built a fast setup/deploy path: a `Makefile` `deploy` target for updates plus `configs/bootstrap.sh` for first-time setup, backed by systemd unit files and an nginx site. GitHub integration and OpenCode auth — the main pain point — are handled via the `.env` file consumed by the systemd `EnvironmentFile`. Docker support from MNT-106 remains an alternative. Implemented incrementally as a research-flavored ticket.

---

## Overview

Deploying Demetra manually was slow, and wiring up GitHub integration and OpenCode auth on a fresh host was the painful part. The result is a Makefile target for repeatable deploys and a bootstrap script for first setup.

## Step 1 — Makefile deploy target

**File:** `Makefile`

The `deploy` target runs, in order:

- `git pull --ff-only`
- `uv sync`
- `alembic upgrade head`
- `bun install` + `bun run build` in `react`
- `daemon-reload` and restart of `demetra-api`, `react`, `watcher`, `listener`, and `worker@1..4`
- nginx reload

## Step 2 — Bootstrap script

**File:** `configs/bootstrap.sh`

On first setup the script symlinks, enables, and starts the systemd services (`configs/services/*.service`) and the nginx site (`configs/nginx.conf`).

## Step 3 — Auth via environment file

GitHub integration and OpenCode auth are the main setup pain point. Credentials live in the `.env` file, which the systemd services consume through `EnvironmentFile` — no interactive auth prompts during deploy.

## Step 4 — Alternative: Docker

Docker support added in MNT-106 provides an alternative deployment path to the systemd setup; a full compose stack on the `mantiby/demetra` image is documented in [[2026-08-10-docker-compose-deploy]].

## Test Results

Validated by running the bootstrap script on a fresh host and exercising the `deploy` target end to end.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-119 — Project deploy script (Linear)](https://linear.app/mnt/issue/MNT-119)
