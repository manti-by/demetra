---
title: 'MNT-323: Swap RQ workers between two generations on deploy'
generated: {by: demetra, at: '2026-11-25T00:00:00Z'}
description: The session implemented blue-green worker deployment to eliminate queue-drain waits during deploys, enabling immediate new generation starts while old ones drain gracefully, maintaining full queue capacity throughout.
type: implementation
status: stable
session_id: ses_dec5c8c34ffeC0aGwaqNcUVfpE
services: [.env.docker, AGENTS, Makefile, README, library, daemons/deploy_lock, daemons/deploy_support, daemons/deployer, daemons/worker_swap, persistence/queue, settings, worker_swap.py, docker-compose, pyproject, test_deploy_lock, test_deployer, test_docker_compose, test_entrypoints, test_queue, test_worker_swap, uv, .sessions, INDEX, 2026-11-25-mnt-323-worker-generation-swap]
branch: mnt-323-swap-rq-workers-between-two-generations-on-deploy
tickets: [MNT-323]
tags: [wiki, infrastructure, feature]
related: [2026-11-25-deploy-deadlock-container-cleanup.md, 2026-11-14-mnt-315-auto-deploy-on-master-commits.md, 2026-11-12-scale-workers-without-recreate.md, 2026-08-10-docker-compose-deploy.md]
---

# MNT-323: Swap RQ workers between two generations on deploy

## TL;DR

This session implemented blue-green worker deployment to eliminate the queue-drain wait during deploys. Workers now run as two Compose services (`worker-blue`/`worker-green`) that swap generations: the new generation starts immediately while the old one drains gracefully. The deploy no longer waits for workflows to complete, maintaining full queue capacity throughout.

## Overview

The change replaces the single `worker` service with two generations that share a common Compose anchor. Key components:

- New `worker_swap.py` module handles the generation swap logic
- Deploy state tracks the live generation
- Manual and automatic deploy paths both use the same swap mechanism
- Workers receive a single TERM signal to finish current jobs
- Hung workflows are force-killed after timeout

## Step 1 — Compose service definition

**File:** docker-compose.yaml

The worker services share a common anchor definition while maintaining separate scaling:

```yaml
x-demetra-worker: &worker
  image: mantiby/demetra:${TAG:-latest}
  command: python -m demetra.worker
  deploy:
    replicas: 4

worker-blue:
  <<: *worker
  restart: unless-stopped

worker-green:
  <<: *worker
  restart: unless-stopped
```

## Step 2 — Worker swap implementation

**File:** demetra/services/daemons/worker_swap.py

Core swap logic:
1. Starts staging generation at full scale
2. Signals live generation exactly once
3. Disables restart policy on draining workers
4. Updates deploy state to new live generation

```python
def swap_workers(live_slot: WorkerSlot) -> bool:
    staging_slot = live_slot.other()
    if not start_service(staging_slot):
        return False
    
    if not signal_workers(live_slot):
        return False
    
    if not disable_restart(live_slot):
        return False
    
    return update_deploy_state(live_slot=staging_slot)
```

## Step 3 — Deploy integration

**File:** demetra/services/daemons/deployer.py

The deployer now:
- Skips queue-drain check
- Starts non-worker services first
- Runs worker swap as final step
- Reaps old generation on next cycle

```python
async def deploy_commit(self) -> None:
    await self._pull_and_build()
    await self._run_one_shot_tasks()
    await self._up_non_worker_services()
    await self._swap_workers()  # Takes deploy lock
    await self._reload_nginx()
```

## Test Results

All 1750 tests passed, including new worker swap integration tests that verify:
- Staging starts before signaling live generation
- No double-signaling of containers
- Legacy worker handling on first swap
- Timeout enforcement for hung workflows
- State persistence across partial failures

## Follow-ups

- Monitor worker swap performance in production
- Verify container reaping on subsequent cycles

## References
- External: [MNT-323: Swap RQ workers between two generations on deploy](https://linear.app/mnt/issue/MNT-323/swap-rq-workers-between-two-generations-on-deploy)
- Related: [2026-11-25-deploy-deadlock-container-cleanup](/pages/2026-11-25-deploy-deadlock-container-cleanup.md)
- Related: [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
- Related: [2026-11-12-scale-workers-without-recreate](/pages/2026-11-12-scale-workers-without-recreate.md)
- Related: [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md)
