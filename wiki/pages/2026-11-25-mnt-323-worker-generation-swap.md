---
title: 'MNT-323: Swap RQ workers between two generations on deploy'
generated: {by: demetra, at: '2026-11-25T17:35:09Z'}
description: Implements a blue/green worker swap in the deploy daemon and manual deploy path, with exactly-once drain signals, later-cycle reaping and a hung-workflow watchdog that requeues abandoned jobs.
type: implementation
status: stable
session_id: ses_dec5c8c34ffeC0aGwaqNcUVfpE
services: [.env.docker, AGENTS, Makefile, README, library, daemons/deploy_lock, daemons/deploy_support, daemons/deployer, daemons/worker_swap, persistence/queue, settings, worker_swap.py, docker-compose, pyproject, test_deploy_lock, test_deployer, test_docker_compose, test_entrypoints, test_queue, test_worker_swap, uv, .sessions, INDEX]
branch: mnt-323-swap-rq-workers-between-two-generations-on-deploy
tickets: [MNT-323]
tags: [wiki, infrastructure, feature, deploy, docker, compose, workers, rq, blue-green, watchdog]
related: [2026-11-25-deploy-deadlock-container-cleanup.md, 2026-11-12-scale-workers-without-recreate.md, 2026-11-14-mnt-315-auto-deploy-on-master-commits.md, 2026-08-10-docker-compose-deploy.md]
---

# MNT-323: Swap RQ workers between two generations on deploy

## TL;DR

Deploys no longer wait for the RQ queue to drain. Workers now run as two Compose generations, `worker-blue` and `worker-green`, with the live slot persisted in `DeployState`. A deploy starts the staging slot on the new image, sends exactly one SIGTERM to each live container so RQ drains the workflow it holds, and reaps the retired generation on a later poll. The manual `make deploy` path runs the same swap through a one-shot `worker-swap` service; a watchdog force-stops a workflow that outlives the job timeout and requeues its job. All 1750 tests pass.

## Overview

The old sequence drained the whole queue (waiting up to `DEPLOY_DRAIN_TIMEOUT`, one hour) before `--force-recreate` stopped every container. A queued workflow could abort a deploy, and a running workflow could block it for the length of a job. The research that preceded this change compared three options — a two-slot Compose blue/green swap inside the existing deploy daemon, Docker Swarm mode, and third-party rolling-deploy helpers — and chose the two-slot swap: RQ already drains the running job on the first SIGTERM, so the deploy no longer has to wait for a workflow to finish. The design is Solution A from that research: hand-roll the swap inside the existing deployer and reuse the deploy lock, the state file and RQ's warm shutdown. The CI gate, the lock and the migration are unchanged.

## Step 1 — Two worker slots and a one-shot swap service

**File:** `docker-compose.yaml`

`x-demetra-worker` extends `x-demetra-app` and carries the worker command, `stop_grace_period` and `deploy.replicas: 4`. Both generations use the anchor:

```yaml
  worker-blue:
    <<: *demetra-worker

  worker-green:
    <<: *demetra-worker
```

The `worker-swap` one-shot runs `python -m demetra.worker_swap --checkout ${DEPLOY_HOST_CHECKOUT:-...}` as root from the built image, mounting the Docker socket, the host checkout and `demetra_deployer_data` so it reads and writes the *same* state file as the daemon. Its `DEPLOY_STATE_PATH` is interpolated from the environment with the usual default rather than hardcoded, so an operator override cannot make the one-shot and the daemon disagree about which generation is live. This is how `make deploy` gets the same swap without duplicating its logic.

## Step 2 — Persist the live generation and the drain bookkeeping

**File:** `demetra/library/models.py`

`DeployState` gained `worker_slot: Literal["blue", "green"]` (default `"blue"`) and `draining_workers: dict[str, float]` mapping a signalled container id to the time of its signal. `DeployState.from_payload` rejects unknown slots and non-finite timestamps, so an older or corrupt state file cannot stop the poll loop.

**File:** `demetra/services/daemons/deploy_support.py`

State load/save and `compose_command` moved here from the deployer so the daemon and the new swap module share them without a circular import. The deployer re-imports the functions, keeping the patch points used by its tests. `save_state` writes a uniquely named temp file in the same directory and renames it over the target, because a truncated state file would reset `worker_slot` to blue and make the next swap force-remove the actually-live generation.

## Step 3 — Swap, reap and watchdog

**File:** `demetra/services/daemons/worker_swap.py`

`swap_workers` first frees the staging slot with `retire_staging_workers`: if an earlier generation is still draining there (a workflow can outlive several five-minute deploys), it disables Docker's restart policy, sends a second TERM (RQ's cold shutdown) and force-removes those containers so Compose actually creates containers from the new image instead of reusing the unchanged image tag. The job they held is recovered by requeueing on a later maintenance cycle. Then staging starts with `up --detach --no-deps --scale worker-green=4 worker-green`, and `docker update --restart no` plus `docker kill --signal=TERM` go only to live containers whose ids are *not* already in `draining_workers`. TERMs are sent one container at a time and each id is persisted as soon as its signal succeeds, so a partial batch failure cannot re-signal a container that already switched RQ to the cold-shutdown handler. Disabling the restart policy first matters: workers inherit `restart: unless-stopped` from the Compose base, so without it Docker would revive a signalled worker on the old image as soon as RQ exited it. One TERM is RQ's warm shutdown: the worker stops dequeuing and finishes its current workflow. A second TERM is deliberately reserved for escalation. On a stack still running the old single `worker` service, those containers are found by Compose labels (the service no longer exists in the file) and signalled once as the initial live generation.

`reap_service` removes only containers listed with `--filter status=exited` and scales a slot to zero only when it has no running containers and is not the live slot, so a draining container is never stopped a second time. `maintain_workers` runs this for both slots and the legacy service at the start of every cycle, under the deploy lock, and reloads the state afterwards.

`escalate_draining_workers` compares the signal time against `SUBPROCESS_TIMEOUT + 60`. For an overdue container it sends a second TERM (RQ kills the work horse) and refreshes the timestamp so it is never re-signalled. `requeue_abandoned_jobs()` runs on **every** maintenance cycle instead: RQ refreshes a running job's registry expiry from the worker heartbeat, so immediately after a force stop its entry is not expired yet and an immediate requeue would find nothing. The idempotent retry on a later cycle requeues the job before RQ's cleanup can move it to the failed registry.

`list_container_ids` returns `None` on a failed `docker ps`, not an empty list. A failed query now aborts the swap before `worker_slot` flips, so a transient Docker error cannot leave the old generation live and undequeued with the deploy recorded as successful.

**File:** `demetra/services/persistence/queue.py`

`requeue_abandoned_jobs()` reads the raw expired members of `StartedJobRegistry` with `zrangebyscore` on `registry.key`, fetches each parsed job and enqueues it again, then deletes exactly those raw members. It deliberately does **not** use `StartedJobRegistry.requeue()`: in rq 2.10 the registry stores `{job_id}:{execution_id}` members while that helper removes only the bare id, so it always raises `InvalidJobOperation`. `remove_executions()` is no better because it resolves members through the execution registry, whose entries outlive the started score — that misses the member being expired and can raise `ValueError` during the gap. Deleting the raw members also prevents the same job being requeued on every later cycle. Malformed members and per-job `ValueError`s are logged and skipped; RQ's own `cleanup()` would otherwise have moved the jobs to the failed registry.

## Step 4 — Remove the drain waits from both deploy paths

**File:** `demetra/services/daemons/deployer.py`

`is_queue_drained`, `wait_for_queue_drain` and the `DEPLOY_DRAIN_TIMEOUT` config are gone. `build_deploy_steps` now force-recreates only `DEPLOY["compose_services"]` (`api`, `watcher`, `listener`, `rq-dashboard`) with `--no-deps`; `run_deploy` calls `swap_workers` after a successful migration and before that `up`. `run_deploy_cycle` calls `maintain_workers` first, keeps the CI gate and the lock, and no longer re-reads the remote sha after a drain. `deploy_lock_timeout` budgets `SWAP_STEP_BUDGET` extra steps for the swap commands.

**File:** `demetra/services/daemons/deploy_lock.py`

`manual_deploy_timeout` now equals the daemon's lease; the old subtractions of the unused drain budget are gone.

**File:** `Makefile`

`deploy-steps` calls `$(MAKE) worker-swap` between the migration and the nginx reload. `docker-up` starts `worker-blue` at 4 and `worker-green` at 0 for fresh stacks.

## Test Results

- `uv run pytest tests/` — 1750 passed, including the new `tests/test_worker_swap.py` (slot helpers, command shapes, exactly-once signalling, staging retirement, staging-before-signal order, reap guards, watchdog, requeue and query-failure aborts) and updated deployer, deploy-lock, queue, compose and entrypoint tests.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check`, `uv run bandit -c pyproject.toml .`, `uv run pre-commit run --all-files` — all pass.
- `docker compose --env-file .env.docker config -q` — valid; a temporary `.env.docker` copied from the example was used because the worktree has no real env file, then removed.
- `make check-migrations` could not run here: `migrations/env.py` builds its URL from `DATABASE` settings rather than the Makefile's `-x url=sqlite:///:memory:`, and no PostgreSQL server is reachable in this worktree. The migration itself was not changed.

## Update — 2026-11-25 18:12

A review found three overlap/failure holes in the first implementation, all fixed before staging:

- A staging slot still held by a draining workflow made Compose reuse old containers, so the deploy succeeded without shipping new code; `retire_staging_workers` now force-stops and removes them first, with their jobs recovered by requeue.
- Requeueing immediately after a force stop found no expired registry entries because a live worker refreshes the expiry from its heartbeat; requeueing now runs on every maintenance cycle.
- `list_container_ids` conflated a failed `docker ps` with an empty slot; it now returns `None` and the swap aborts instead of flipping the live slot on bad data.
- A second review found that an in-place state write could be truncated by a crash, resetting the live slot to blue; `save_state` now writes a temp file in the same directory and renames it over the target.
- A failed `docker kill` in a batch left earlier successful ids unrecorded, so a retry would cold-shutdown them; each id is now persisted immediately after its own TERM.
- A third review found that `StartedJobRegistry.requeue()` never matches RQ 2.10's composite registry members, so force-killed jobs were never requeued; the job's executions are now removed explicitly before `queue.enqueue_job()`. The one-shot's `DEPLOY_STATE_PATH` is also interpolated from the environment so it cannot disagree with the daemon's state file.
- A fourth review found that even `remove_executions()` reads the wrong registry: its entries outlive the started score, so force-killed jobs were either skipped or requeued on every cycle. The exact raw expired members read from the started registry are now deleted after enqueue, with `ValueError` guarded per member and per job.

## Follow-ups

- Monitor worker swap performance in production.
- A host-side nginx reload hook is still needed before nginx config changes can ship from the daemon; the in-container `nsenter` reload remains optional and currently fails (see [the deploy deadlock page](/pages/2026-11-25-deploy-deadlock-container-cleanup.md)).
- Two worker generations run at once during a swap, so future migrations must stay expand/contract until the old generation has drained.
- Consider making `make docker-up` read the live slot from the state file instead of defaulting to blue.

## References

- External: [MNT-323: Swap RQ workers between two generations on deploy](https://linear.app/mnt/issue/MNT-323/swap-rq-workers-between-two-generations-on-deploy)
- Related: [Deploy deadlock from an interrupted recreate](/pages/2026-11-25-deploy-deadlock-container-cleanup.md)
- Related: [Scaling RQ workers without recreating running containers](/pages/2026-11-12-scale-workers-without-recreate.md)
- Related: [MNT-315: Auto deploy on master commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
- Related: [Docker Compose deploy](/pages/2026-08-10-docker-compose-deploy.md)
