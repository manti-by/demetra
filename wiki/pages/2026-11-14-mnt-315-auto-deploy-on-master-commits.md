---
title: 'MNT-315: Auto deploy on master commits'
date: '2026-11-14'
type: implementation
status: resolved
session_id: ses_e25708f3cffeIdPEZjNp0Mwatw
services: [.env.docker, AGENTS, Dockerfile, Makefile, README, deployer.py, library, daemons/deployer, settings, docker-compose, pyproject, test_deployer, test_docker_compose, test_dockerfile, test_entrypoints, uv, INDEX, 2026-11-14-mnt-315-auto-deploy-on-master-commits]
branch: mnt-315-auto-deploy-on-master-commits
tickets: [MNT-315]
tags: [wiki, infrastructure, feature]
related: [2026-08-10-docker-compose-deploy.md, 2026-07-07-project-deploy-script.md, 2026-09-28-compose-langsmith-host-env.md]
---

# MNT-315: Auto deploy on master commits

## TL;DR

Implemented an auto-deploy daemon that watches `origin/master` and triggers deployments when new commits pass CI checks and the job queue drains. The deployer runs as a privileged container with host Docker access, persists state between runs, and handles self-updates safely. All tests pass, and a follow-up ticket exists to merge this with other watchers.

## Overview

The deployer daemon (`demetra/deployer.py`) follows the same pattern as the existing watcher/listener services but with additional safety checks and host system integration:

1. Polls `origin/master` via `git ls-remote`
2. Validates CI status through GitHub's API
3. Waits for the RQ default queue to drain
4. Runs the deploy sequence against the host checkout
5. Persists state between runs to handle failures gracefully

**Key constraints:**
- Must access host Docker daemon and nginx
- Must not interfere with running jobs
- Must handle its own container updates safely

## Step 1 — Deployer Service Setup

**File:** `docker-compose.yaml`
Added the privileged `deployer` service with:
- Host Docker socket access (`/var/run/docker.sock`)
- Host checkout bind-mount at same path
- SYS_ADMIN capability for nginx reload
- Dedicated state volume (`demetra_deployer_data`)

**Security measures:**
- Runs baked `/opt/demetra/src` copy (read-only)
- Never mounts app home volume
- Self-recreates after successful deploy

## Step 2 — Docker Tooling

**File:** `Dockerfile`
Added version-pinned Docker CLI and Compose v2:
```dockerfile
ARG DOCKER_CLI_VERSION=27.3.1
ARG DOCKER_COMPOSE_VERSION=v2.29.7
RUN curl -fsSL "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" -o /tmp/docker.tgz \
    && tar -xzf /tmp/docker.tgz -C /tmp docker \
    && mkdir -p /tmp/docker-cli-plugins \
    && curl -fsSL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
      -o /tmp/docker-cli-plugins/docker-compose \
    && chmod +x /tmp/docker-cli-plugins/docker-compose \
    && rm /tmp/docker.tgz
```

## Step 3 — Configuration

**File:** `.env.docker.example`
Added deployer settings with safety defaults:
```ini
DEPLOY_HOST_CHECKOUT=/home/manti/www/demetra
DEPLOYER_POLL_INTERVAL=60
DEPLOY_MIN_INTERVAL=300
DEPLOY_DRAIN_TIMEOUT=3600
DEPLOY_STEP_TIMEOUT=3600
DEPLOY_STATE_PATH=/var/lib/demetra/deployer-state.json
DEPLOY_NGINX_RELOAD_COMMAND=nsenter -t 1 -m -p -- service nginx reload
```

## Step 4 — Core Logic

**File:** `demetra/services/daemons/deployer.py`
Implements the state machine with:
- SHA detection (`get_remote_master_sha`)
- CI status checks (`get_ci_status`)
- Queue draining (`wait_for_queue_drain`)
- Deploy steps (`run_deploy`)
- State persistence (JSON file)
- Self-update mechanism

## Test Results

All 1428 tests pass, including new deployer-specific tests:
- Service integration
- State persistence
- Safety checks
- Error handling

Manual verification confirmed:
- Successful deploys on new commits
- Queue draining before deploy
- Failed deploy logging
- Self-update behavior

## Follow-ups

- [[MNT-316]] to merge watcher/listener/deployer into one universal watcher

## References
- External: https://linear.app/mnt/issue/MNT-315/auto-deploy-on-master-commits
- Related: [[2026-08-10-docker-compose-deploy]]
- Related: [[2026-07-07-project-deploy-script]]
- Related: [[2026-09-28-compose-langsmith-host-env]]
