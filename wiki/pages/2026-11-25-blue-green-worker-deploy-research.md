---
title: Blue-green worker deployment research for the home Ubuntu server
generated: {by: demetra, at: '2026-11-25T00:00:00Z'}
description: Records the research into zero-downtime container deploys for the Demetra home server, comparing a two-slot Compose blue/green worker swap in the existing deployer, Docker Swarm mode and third-party rolling-deploy helpers, and recommending the two-slot swap because RQ already provides warm-shutdown job draining.
type: investigation
status: stable
session_id: ses_decf71ecfffe4EvN6H5oFK4ODM
services: [deploy, daemons, persistence, configs]
branch: '-'
tickets: [MNT-323]
tags: [deploy, docker, compose, workers, rq, blue-green, rolling-update, swarm, research]
related: [2026-11-25-deploy-deadlock-container-cleanup.md, 2026-11-14-mnt-315-auto-deploy-on-master-commits.md, 2026-11-12-scale-workers-without-recreate.md, 2026-08-10-docker-compose-deploy.md]
---

# Blue-green worker deployment research for the home Ubuntu server

## TL;DR

- **The blocking part of a deploy is the queue drain, not the container recreate.** The daemon
  waits up to `DEPLOY_DRAIN_TIMEOUT` (1 h) for the RQ queue to be *completely* empty and aborts the
  deploy when it is not; the recreate itself would already be graceful, because RQ treats the
  first `SIGTERM` as a warm shutdown and finishes the running job before exiting.
- **Docker Compose has no rolling updates.** `deploy.update_config` (including `order: start-first`)
  is parsed but ignored outside Swarm — Compose 5.6 only warns about it. Blue/green therefore has
  to be hand-rolled, delegated to Swarm, or delegated to a third-party helper.
- **Recommended: a two-slot (`worker-blue` / `worker-green`) Compose swap inside the existing
  deploy daemon.** Start the new generation, `SIGTERM` the old one (RQ drains the running job in
  the background), reap the drained containers on a later cycle. No new infrastructure, reuses the
  deploy lock and the deployer, and it removes the drain wait entirely.
- **Swarm mode is the "batteries included" option** (native `start-first` rolling updates, health
  checks, auto-rollback) but it is a real infrastructure change: the host enters swarm mode, the
  compose file loses `build`/`container_name`/`depends_on`, and named volumes get the stack-name
  prefix (the Postgres data volume would have to be migrated).
- **k8s/k3s is overkill.** The interesting primitive — "stop taking new work, finish what you
  hold" — is already inside RQ; the orchestration on top of it is what is being bought.

---

## Net effect

A deploy should never have to wait for a workflow to end. Today it does, twice: once because the
daemon drains the whole queue before recreating anything, and once because the recreate of a busy
worker waits for that worker to finish its job. The first wait is unnecessary, the second is
desired but must not block the deploy of everything else.

The practical target state:

- Idle workers and every non-worker service (api, watcher, listener, rq-dashboard) are replaced
  with the new image **immediately** after the migration.
- A worker that is mid-workflow is signalled once, finishes that workflow on the old image, and
  is reaped afterwards. The queue keeps its full capacity the whole time because the new
  generation is already running.
- The deploy lock is still held for the whole operation, but for minutes instead of hours.

---

## Why the deploy blocks today

**File:** `demetra/services/daemons/deployer.py:640` (`wait_for_queue_drain`)

```python
async def wait_for_queue_drain(timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while not is_queue_drained():
        if time.monotonic() >= deadline:
            logger.warning(f"Job queue still busy after {timeout} seconds, skipping this deploy")
            return False
        await asyncio.sleep(DRAIN_POLL_INTERVAL)
    return True
```

`is_queue_drained()` requires `queue.count == 0` **and** an empty started-job registry — i.e. not
only "no job running" but "no job waiting". A queued-but-not-started workflow is enough to abort
the deploy for an hour.

**File:** `demetra/services/daemons/deployer.py:706` (`run_deploy`)

```python
for name, command in build_deploy_steps(checkout_path=checkout_path, sha=sha):
    if name == RECREATE_STEP and not await wait_for_queue_drain(timeout=DEPLOY["drain_timeout"]):
        logger.error("Job queue busy again while preparing the deploy, deferring the container recreate")
        return False
```

**File:** `demetra/settings.py:221`

```python
"drain_timeout": env_get_int("DEPLOY_DRAIN_TIMEOUT", 3600),
```

The recreate step itself is:

**File:** `demetra/services/daemons/deployer.py:294` (`build_deploy_steps`)

```python
(
    "up",
    [*compose, "up", "--detach", "--force-recreate", "--scale", "worker=4", *DEPLOY["compose_services"]],
),
```

`--force-recreate` stops every container of every listed service before recreating it. Compose
stops a container by sending `SIGTERM` and waiting for `stop_grace_period`, so the *worker*
replacement is already job-safe — but it is a **blocking** wait, and the daemon reaches it only
after the queue drained.

The manual path (`make deploy`, `Makefile:29`) has no drain at all; it goes straight to
`--force-recreate` and therefore blocks on the busy worker instead of on the queue. Both paths
need the same "signal once, do not wait" treatment.

---

## What the platform already gives you for free

### RQ drains the running job on the first SIGTERM

**File:** `rq/worker/base.py` (rq 2.10.0, pinned in `pyproject.toml:31`)

```python
def request_stop(self, signum, frame):
    """Stops the current worker loop but waits for child processes to
    end gracefully (warm shutdown)."""
    self._shutdown_requested_date = now()
    signal.signal(signal.SIGINT, self.request_force_stop)
    signal.signal(signal.SIGTERM, self.request_force_stop)
    self.handle_warm_shutdown_request()
    self._shutdown()

def _shutdown(self):
    if self.get_state() == WorkerStatus.BUSY:
        self._stop_requested = True
        self.set_shutdown_requested_date()
        self.log.debug('Worker %s: stopping after current horse is finished. ...')
```

and in the main loop:

```python
if self._stop_requested:
    self.log.info('Worker %s: stopping on request', self.name)
    break
```

Consequences for the deploy design:

- **One `SIGTERM` = warm shutdown.** The worker stops dequeuing, the work horse finishes the
  current workflow, the parent then exits. The job lands in the finished registry — it is never
  re-queued and never lost.
- **A second `SIGTERM` = cold shutdown.** `request_stop` re-registers `SIGTERM`/`SIGINT` with
  `request_force_stop`, which kills the horse immediately and fails the job. The drain step must
  therefore signal each container **exactly once**, and the cleanup step must never `docker stop`
  a container that is already draining.
- The work horse ignores `SIGINT` and keeps the default `SIGTERM` handler, but Docker only
  signals PID 1, so the horse is never signalled directly — only the parent is.

### The grace period is already sized for the longest job

**File:** `docker-compose.yaml:107`

```yaml
    # A workflow job runs for up to the queue default_timeout
    # (SUBPROCESS_TIMEOUT, four hours by default). ...
    stop_grace_period: ${WORKER_STOP_GRACE_PERIOD:-14460s}
```

`SUBPROCESS_TIMEOUT` is 4 h and the queue's `default_timeout` is derived from it
(`demetra/services/persistence/queue.py:9`), so the grace covers the longest possible job. If the
grace were shorter, Docker's `SIGKILL` would kill the horse and the job would end up in the
failed registry with "Work-horse terminated unexpectedly".

### Scaling without recreating is already verified

**File:** `wiki/pages/2026-11-12-scale-workers-without-recreate.md`

`docker compose up -d --scale worker=4 --no-recreate worker` adds workers to the live stack
without touching the running ones. The same flags are the seed of the swap below: `--no-recreate`
suppresses the recreate of containers whose config changed, `--scale` adds capacity.

### Compose anchors make a second worker service cheap

**File:** `docker-compose.yaml:12` (`x-demetra-app`), already used by `worker`, `watcher` and
`listener`, which differ only in `command` and `LOG_PATH`.

---

## Solution A — Two-slot (blue/green) worker swap inside the existing deployer

**Shape:** two Compose services (`worker-blue`, `worker-green`) from the same anchor. One is the
live generation, the other is the staging generation. Every deploy starts the staging generation
with the new image, drains the live one and swaps the roles.

### The compose change

```yaml
x-demetra-worker: &demetra-worker
  <<: *demetra-app
  command: ["python", "-m", "demetra.worker"]
  stop_grace_period: ${WORKER_STOP_GRACE_PERIOD:-14460s}
  environment:
    <<: *demetra-env
    LOG_PATH: /var/log/demetra/worker.log

services:
  worker-blue:
    <<: *demetra-worker
  worker-green:
    <<: *demetra-worker
```

`DEPLOY["compose_services"]` drops `worker` (the slots get their own steps), and the
`--scale worker=4` flag becomes `--scale worker-blue=4` / `--scale worker-green=4`.

### The deploy steps

```bash
# 1. build the new image (existing step) and run the migration (existing step)

# 2. start the staging generation with the new image; the live generation keeps running
docker compose --project-directory "$CHECKOUT" --env-file "$CHECKOUT/.env.docker" \
  up --detach --no-deps --scale worker-green=4 worker-green

# 3. drain the live generation: exactly one SIGTERM per container, no waiting
docker kill --signal=TERM $(docker compose ... ps -q worker-blue)

# 4. reap on a later cycle: remove only containers that already exited
docker rm $(docker compose ... ps -aq --filter status=exited worker-blue)
docker compose ... up --detach --no-deps --scale worker-blue=0 worker-blue
```

Step 3 uses `docker kill --signal=TERM` rather than `docker stop` on purpose: `docker kill` sends
the signal and returns, while `docker stop` waits for the grace period and then escalates to
`SIGKILL`. A busy worker therefore keeps running its workflow in the background while the deploy
proceeds. Step 4 must never call `docker stop` on a container that is still draining — that
second signal is the cold shutdown described above.

The role of each slot is persisted in `DeployState` (`demetra/library/models.py:331`) as a single
`worker_slot: "blue" | "green"` field, toggled after every successful swap. The reap step runs at
the start of every poll cycle, so a worker that drains hours later is cleaned up on its own.

### Flow of a deploy

- **Pull → build → migrate** — unchanged.
- **Idle services** (`api`, `watcher`, `listener`, `rq-dashboard`) — recreated immediately with
  `--force-recreate`, exactly as today.
- **Staging worker generation** — started with the new image; it registers itself in RQ and
  picks up new jobs straight away.
- **Live worker generation** — one `SIGTERM` per container. Idle workers exit at once; the busy
  one finishes its workflow and exits.
- **Queue capacity** — never below 4 during the swap (4 staging + 4 live, briefly 5–8).
- **Reap** — on the next cycle, the exited live containers are removed and the slot is scaled to 0.

### Pros

- **No new infrastructure.** No daemon, no agent, no control plane, no second Docker host. The
  deploy lock, the deploy state file and the CI gate stay exactly as they are.
- **Reuses the RQ semantics that already exist.** The hard part — "finish the job you hold" — is
  RQ's, not new code. The deployer only sequences it.
- **The deploy stops blocking.** `wait_for_queue_drain` can be dropped entirely; the drain
  timeout stops being the deploy's worst-case duration.
- **Explicit and inspectable.** `docker compose ps` shows both generations; the state file says
  which one is live. A failed swap is visible instead of silent.
- **Small diff.** One anchor plus two services in the compose file, one new field in
  `DeployState`, two or three new steps in the deployer, one test file touched
  (`tests/test_docker_compose.py:14` lists the service names).

### Cons

- **Custom code to maintain.** The swap logic, the slot bookkeeping and the reap step are ours.
- **Two generations of code run at once.** Every Alembic migration must be expand/contract:
  the old worker keeps querying the old schema while the new worker uses the new one. A
  destructive migration (drop/rename a column) breaks the draining worker.
- **Twice the workers for the duration of the swap** — the host needs headroom for 8 worker
  containers instead of 4.
- **The old container keeps its slot until it exits.** If a workflow hangs, the old generation
  lingers; a watchdog is needed to escalate to `SIGKILL` after `SUBPROCESS_TIMEOUT`.
- **The blue/green discipline is manual** for the api: recreating the api container is a
  sub-second outage, so a true blue/green for the api needs an nginx upstream switch (the host
  nginx proxies to `127.0.0.1:8001`, `configs/nginx.conf`), and the in-container nginx reload is
  currently broken anyway (see the deploy-deadlock page).

---

## Solution B — Docker Swarm mode

**Shape:** `docker swarm init` on the host, then `docker stack deploy -c docker-compose.yaml
demetra` instead of `docker compose up`. Swarm implements the Compose Deploy Specification for
real, including the rolling update that Compose ignores:

```yaml
deploy:
  update_config:
    parallelism: 4
    delay: 10s
    order: start-first        # new task starts before the old one is stopped
    monitor: 30s
    failure_action: rollback
    max_failure_ratio: 0
  restart_policy:
    condition: any
```

`order: start-first` is exactly the blue/green primitive: the new task starts, the old task
receives `SIGTERM` and drains under `stop_grace_period`, and Swarm rolls the service back
automatically if the new task fails its health check. `docker service rollback` is a one-liner.

### Pros

- **Native, no custom code.** The rolling update, the health checks, the `monitor` window, the
  failure ratio and the automatic rollback are all built into the Docker Engine.
- **Correct by construction.** Swarm knows which task is which generation; there is no slot
  bookkeeping, no image-id comparison, no reap step.
- **Same file.** The compose file stays; it gains a `deploy:` block and loses the keys Swarm
  ignores.
- **A path to more than one host** if the home server ever grows.

### Cons

- **It is a real infrastructure change.** `docker swarm init` turns the host's Docker into a
  swarm node: overlay networks, the routing mesh for published ports, a manager quorum, and the
  swarm state in the Raft log. Every `docker compose` invocation on that host then warns that the
  engine is in swarm mode.
- **The compose file loses functionality.** Swarm ignores `build` (the image must exist
  beforehand — fine, the daemon builds it on the host), `container_name` (`postgres` and `redis`
  set one), `depends_on` (the `migrate` → `service_completed_successfully` ordering and the
  healthy `postgres`/`redis` gates are dropped; the app would have to retry instead), and the
  top-level `restart` (it moves to `deploy.restart_policy`).
- **The data volumes are renamed.** Swarm prefixes volumes with the stack name, so
  `demetra_postgres_data` becomes `demetra_demetra_postgres_data`. The Postgres data directory
  has to be migrated by hand.
- **The deployer daemon becomes a swarm task.** It mounts the Docker socket and the host
  checkout and shells out to `docker compose`; under swarm it would have to shell out to
  `docker stack deploy` / `docker service update` instead, and the self-recreate helper
  (`recreate_deployer_command`) has to be rewritten.
- **The rolling update still waits for the old task.** Swarm's updater blocks until the old task
  exits (the `defaultOldTaskTimeout` is one minute in older SwarmKit, `stop_grace_period` in
  current versions), so the deploy command has to run detached (`-d`) and the convergence be
  polled instead of waited on.
- **Swarm is in maintenance mode.** Docker ships no new Swarm features; it is stable but frozen.

### Verdict

Right tool if the host ever runs more than one machine or more than a handful of services.
Today it is a large, risky migration (volumes, `depends_on`, the deployer itself) for a
primitive that RQ already gives us for free.

---

## Solution C — A third-party rolling-deploy helper (or Nomad)

### C1 — A helper that implements `deploy.update_config` for plain Compose

Examples: `dokku/docker-orchestrate` (reads `deploy.update_config` from the compose file and
replaces containers one at a time) or the `majidkabir/docker-compose-rolling-update` shell
scripts (scale up with `--no-recreate --scale`, wait for the new containers to be healthy, then
stop the old ones).

**Pros**

- No changes to the compose file beyond adding `deploy.update_config` and a `healthcheck`.
- Small, auditable surface; the same "scale up, then drain" mechanics as Solution A, but written
  and tested by somebody else.
- The helper's `--stop-timeout` defaults to the service's `stop_grace_period`, so the 4 h grace
  is respected.

**Cons**

- **A worker has no meaningful health check.** The helper waits for the new container to report
  healthy before stopping the old one; for an RQ worker "healthy" can only mean "the process is
  up", so the helper adds a step without adding safety.
- **Third-party dependency** for a home server whose deploy path is currently self-contained.
- **The scale-down bookkeeping is the same problem Solution A has** — these helpers manage it,
  but it is the part that breaks silently (the compose container-number assignment).

### C2 — Nomad

Single binary, server and client in one process on the home server, driving the same Docker
daemon. Its update model is exactly the one wanted:

```hcl
job "demetra" {
  group "worker" {
    count = 4
    update {
      max_parallel  = 4
      canary       = 4        # blue/green: keep the old allocations alive
      auto_revert  = true
      health_check = "task_states"
    }
    task "worker" {
      driver = "docker"
      config { image = "mantiby/demetra:latest" }
      kill_timeout = "4h1m"   # lets the RQ worker finish its job
    }
  }
}
```

**Pros**

- Purpose-built for this: `kill_signal`/`kill_timeout` for the drain, `canary` +
  `nomad job promote` for a real blue/green, `auto_revert` for the rollback, `max_parallel` for
  the rollout shape.
- Still "small infrastructure": one binary, one process, no control plane to operate separately.
- Service discovery, health checks and placement come with it.

**Cons**

- **The compose file has to be rewritten** in the Nomad job spec (HCL or jobspec). Postgres,
  Redis, the api, the watcher, the listener, the RQ dashboard and the deployer all become tasks.
  That is the largest single diff of the three options.
- **The deploy daemon becomes a Nomad job** that runs `nomad job run` — an inversion of the
  current design.
- **A second operational surface** (Nomad CLI, job status, allocation logs) next to
  `docker compose ps` and the RQ dashboard.
- Nomad's `kill_timeout` is capped by the agent's `max_kill_timeout` (default 30 s), so the 4 h
  grace needs explicit configuration on the client.

### Verdict

Nomad is the honest "orchestrator lite" answer and it fits a home server well. It is also a
rewrite of the whole deployment surface, which is not what this problem needs — the problem is
the *sequencing* of a worker swap, and RQ already provides the hard part.

---

## Comparison

- **Solution A (two-slot Compose swap)** — smallest diff, no new infrastructure, removes the
  drain wait, but custom code and two code generations live at once.
- **Solution B (Swarm)** — most mature rolling-update machinery, but a host-level migration
  (volumes renamed, `depends_on`/`container_name` dropped, the deployer rewritten) and a frozen
  upstream.
- **Solution C (helper / Nomad)** — least bespoke code, at the price of a new dependency
  (helper) or a new deployment model (Nomad).

Recommendation: **Solution A**, with the api left on a plain recreate for now. It is the only one
that needs no new infrastructure, and the deployer daemon plus the deploy lock it reuses are
already the right place for the sequencing.

---

## Why not Kubernetes (or k3s)

- **The primitive is already owned by RQ.** Kubernetes' `terminationGracePeriodSeconds` +
  `preStop` maps onto RQ's warm shutdown, which the current compose file already implements
  through `stop_grace_period`. k8s would add a second, redundant drain mechanism.
- **The cost is the manifest rewrite**, not the control plane. Every service becomes a Deployment
  plus a Service plus a ConfigMap/Secret, the bind mounts for `.keys/` and the shared
  `demetra_app_data` volume need `hostPath` care, the deployer needs to drive `kubectl` (or
  `rollout undo`), and the local Postgres/Redis would ideally move to a StatefulSet with a
  PVC — a data migration on top of everything else.
- **k3s is smaller but not free**: one more daemon to install, upgrade and back up, plus the
  same manifest rewrite. It buys multi-node scheduling and self-healing, neither of which a
  single home server needs yet.
- The honest reason people reach for k8s is *multi-host scheduling* and *declarative rollback*.
  Demetra has one host; its rollback story is "redeploy the previous sha", which the deployer
  already does by rebuilding the previous commit.

---

## Risks and gotchas

- **Exactly one `SIGTERM` per draining worker.** A second signal is RQ's cold shutdown and kills
  the running workflow. `docker compose up --force-recreate` on a service that contains draining
  workers will send that second signal — the reap step must use `docker rm` on exited containers
  only.
- **`docker kill --signal=TERM` does not escalate.** A worker whose workflow hangs stays alive
  forever; a watchdog that escalates to `SIGKILL` after `SUBPROCESS_TIMEOUT` + margin is needed,
  and the killed job then has to be recovered from the started-job registry.
- **Migrations must be expand/contract.** The draining worker runs the old code against the new
  schema. Never drop or rename a column in the same deploy that changes the code that reads it.
- **The deploy lock lives in Redis.** With Redis stopped, `make deploy` cannot take the lock and
  the deploy that would start Redis never runs — the deadlock recorded in
  [2026-11-25-deploy-deadlock-container-cleanup](/pages/2026-11-25-deploy-deadlock-container-cleanup.md).
  A swap that starts containers before the lock is taken would reintroduce it.
- **An interrupted `compose up` leaves orphans.** The recreate creates a temporary
  hash-prefixed container and then renames it; killing the command in that window leaves
  `Created` containers that a later `compose up` cannot reuse. A swap with more steps has more
  windows, so the reap step should also clean up `Created`/`Exited` orphans of the worker
  services.
- **The nginx reload from inside the container is broken** (`nsenter: Operation not permitted`).
  A blue/green api (new container on port 8002, nginx upstream switch) needs a host-side reload
  hook, which is a separate ticket.
- **Container names change** from `demetra-worker-N` to `demetra-worker-blue-N` /
  `demetra-worker-green-N`. Only `tests/test_docker_compose.py:14` references the service names
  today, but any runbook or dashboard that greps for `demetra-worker-` needs updating.
- **The `deploy.replicas: 4` key is ignored by Compose outside Swarm** — the `--scale` flags on
  the command line are what set the count, in every target.

---

## Open questions

- Should the api get the same two-slot treatment (new container on a second host port, nginx
  upstream switch, reload) or is a sub-second recreate good enough for a single-node home server?
- Should the reap step escalate to `SIGKILL` after `SUBPROCESS_TIMEOUT`, and should the killed
  job be re-enqueued (it currently ends in the failed registry with "Work-horse terminated
  unexpectedly")?
- Does the workflow need to be idempotent for the blue/green overlap to be safe — i.e. can the
  old worker and the new worker ever touch the same task rows at the same time? (The queue
  guarantees one worker per job, but a re-run of the same task after a failure is possible.)
- Should the deployer keep the drain as a *fallback* for the manual `make deploy` path, or should
  both paths call the same swap routine? The manual path currently has no drain at all.

---

## Follow-ups

- ~~File an implementation ticket for Solution A (compose slots + deployer swap steps + reap step),
  referencing this page.~~ **Done 2026-11-25** — [MNT-323](https://linear.app/mnt/issue/MNT-323/swap-rq-workers-between-two-generations-on-deploy)
  "Swap RQ workers between two generations on deploy" (team M2, project Demetra, labels
  Infrastructure + Feature, priority Medium, assignee the Demetra bot). Scope decided there:
  workers only, the hung-workflow watchdog included, the api left on a plain recreate.
- Separately: a host-side nginx reload hook, needed for any api blue/green and for shipping
  nginx config changes.

## References

- Related: [2026-11-25-deploy-deadlock-container-cleanup](/pages/2026-11-25-deploy-deadlock-container-cleanup.md)
- Related: [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
- Related: [2026-11-12-scale-workers-without-recreate](/pages/2026-11-12-scale-workers-without-recreate.md)
- Related: [2026-08-10-docker-compose-deploy](/pages/2026-08-10-docker-compose-deploy.md)
- External: Docker Compose Deploy Specification — <https://docs.docker.com/compose/compose-file/deploy/>
- External: Docker Swarm rolling updates — <https://docs.docker.com/engine/swarm/swarm-tutorial/rolling-update/>
- External: Docker `stack deploy` limitations — <https://docs.docker.com/engine/swarm/stack-deploy/>
- External: RQ workers and shutdown semantics — <https://python-rq.org/docs/workers/>
- External: Nomad rolling updates — <https://developer.hashicorp.com/nomad/docs/job-declare/strategy/rolling>
