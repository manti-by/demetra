---
title: Deploy deadlock from an interrupted recreate and a misconfigured deployer
generated: {by: demetra, at: '2026-11-24T21:50:00Z'}
description: Records repairing a fully down Demetra deployment where an interrupted `docker compose up --force-recreate` left nine containers stuck in `Created` while Redis was stopped, deadlocking the manual deploy lock, and where the containerized deployer could not find the Docker CLI.
type: debug
status: stable
session_id: ses_df094d738ffesVpDYe3Bhnbxly
services: [docker-compose, deployer, deploy_lock, settings, Dockerfile]
branch: master
tickets: []
tags: [deploy, docker, deadlock, infrastructure]
related: [2026-11-14-mnt-315-auto-deploy-on-master-commits.md, 2026-11-12-scale-workers-without-recreate.md]
---

# Deploy deadlock from an interrupted recreate and a misconfigured deployer

## TL;DR

The whole stack was down: an interrupted `docker compose up --force-recreate`
left nine services stuck in `Created` with temporary names and stopped Postgres
and Redis, so `make deploy` could not take its deploy lock and refused to run.
The containerized deployer never worked either — it looked for Docker at
`/usr/bin/docker`, but the image bakes it at `/usr/local/bin/docker`. After
cleaning the containers and pinning `DOCKER_PATH` the deployer built, migrated
and recreated the stack end to end, and the manual lock path was verified.

## Symptom

- `docker compose ps` showed nothing running.
- `docker ps -a` showed nine containers in `Created` state with hash-prefixed
  names: `158bb630e9a2_demetra-api-1`, `06b5ed3aa10f_demetra-worker-1`,
  `9ae12cbbd9b7_demetra-watcher-1`, `5c1969d7e112_demetra-rq-dashboard-1`, and
  similar, alongside the canonical strings for the others.
- `demetra-postgres` and `demetra-redis` had `Exited (0)`.
- `make deploy` aborted immediately with
  `Could not take the deploy lock, aborting (another deploy may be running)`.
- The `demetra-deployer` systemd unit was active, but its log repeated
  `unknown flag: --slurp` and `No deployed revision found` every minute.

## Step 1 — Interrupted recreate left orphaned containers

Every orphan carried `com.docker.compose.replace: <service>-1` and a
`com.docker.compose.project: demetra` label. That is Docker Compose mid-recreate:
it creates the replacement container under a temporary hash-prefixed name, then
removes the old one and renames the replacement. Killing `compose up` in that
window leaves only the temporary-named containers, and the canonical service
name never exists.

The canonical names being absent is what made a second `compose up` useless:
there was nothing to reuse, and the half-created set still held the project
network and service slots. `docker compose down --remove-orphans` removed all of
them, the network and the stopped infra containers.

**Evidence:** `docker inspect` on `d33c896f4dc7` (the stuck `api` replacement)
showed `com.docker.compose.replace: api-1` and `Status: created`, `Pid: 0`.

## Step 2 — The deploy lock depends on the stopped Redis

**File:** `demetra/services/daemons/deploy_lock.py`

`make deploy` wraps its recipe in `python -m demetra.deploy_lock`, which takes
the daemon's `demetra:deployer` key through
`docker compose exec -T redis redis-cli`. The module docstring says it explicitly:
the host has no route to the Redis container, so the key must be written from
inside the container. With Redis stopped, the `exec` fails, `acquire` returns
`None`, and the wrapper exits before running any recipe step. That is the
deadlock: nothing restarts Redis because the deploy that would start it is
waiting on Redis.

There was also a silent split-brain. The host `demetra-deployer` systemd unit
started a native `redis-server` on `localhost:6379`, so the daemon locked and
drained against a different Redis than the containers (`redis://redis:6379/1`).
Manual and automatic deploys therefore never serialized. The repo deliberately
does not publish the container Redis to the host —
`tests/test_docker_compose.py::TestDockerComposeDeployerService::test_redis_is_not_published_to_the_host`
asserts that — so the daemon is meant to run in the `deployer` container.

**Resolution:** stopped and removed the host systemd unit (it was a symlink),
making the compose `deployer` service the only daemon. The host
`redis-server` was left running: it serves other workloads (12 connected
clients) and is unrelated to the container stack.

## Step 3 — Host `gh` cannot gate CI, container `gh` can

**File:** `demetra/services/daemons/deployer.py:519`

`get_ci_status` calls `gh api --paginate --slurp .../check-runs`. The host
package is `gh 2.46.0`, which predates `--slurp`; the image ships
`gh 2.105.0`, which supports it. This is another symptom of the split-brain:
the daemon was designed for the image, not for the host system unit. No code
change was needed once the container deployer was authoritative.

## Step 4 — Container deployer could not find Docker

**File:** `demetra/settings.py:225`

```python
"docker_path": env_get_path("DOCKER_PATH", Path("/usr/bin/docker")),
```

**File:** `Dockerfile:68`

```dockerfile
COPY --from=builder /tmp/docker/docker /usr/local/bin/docker
```

The default `/usr/bin/docker` is correct for the host systemd path but wrong
inside the image. The deployer logged
`Error running the deploy cycle: [Errno 2] No such file or directory: '/usr/bin/docker'`
on every poll, so even after containers were cleaned it could not rebuild or
recreate anything.

**Fix:** `docker-compose.yaml:155` now pins the baked path for the service:

```yaml
DOCKER_PATH: /usr/local/bin/docker
```

The compose file is bind-mounted into the deployer, but the environment comes
from the container's creation, so this requires recreating `deployer` — which
the daemon does itself after a successful deploy.

## Root cause

One interrupted `compose up` removed the running stack, and the lock that
guards deploys lived in the stopped Redis, so no path could self-heal. The
independent `DOCKER_PATH` defect would have blocked the daemon even with Redis
healthy, and the host systemd daemon was never able to coordinate with the
container stack in the first place.

## Resolution / Fix

1. `docker compose down --remove-orphans` removed the nine orphaned `Created`
   containers, the project network and the stopped infra containers.
2. Restarted `postgres` and `redis` with `--wait`, ran the `migrate` and
   `react-build` one-shots to success.
3. Recreated the full stack: `up --detach --force-recreate --scale worker=4
   api worker watcher listener rq-dashboard deployer`.
4. Disabled and removed the host `demetra-deployer` systemd unit.
5. Added `DOCKER_PATH: /usr/local/bin/docker` to the compose `deployer`
   service, committed `826d514` and pushed it (CI green).
6. Removed a stale `.git/REBASE_HEAD` left from an earlier aborted rebase; there
   was no rebase in progress and the tree was clean.
7. Let the deployer run its cycle: `pull` → `build` → `pull_images` →
   `migrate` → `up` → self-recreate. State then held
   `last_deployed_sha: 826d514…`, `pending_recreate: false`, no error.

**Verification:** `uv run python -m demetra.deploy_lock -- true` acquired and
released the manual lock; the `demetra:deployer` key was empty afterwards; the
API returned `200`, the RQ dashboard `200` and `https://demetra.manti.by` `200`;
all 11 containers were up (four workers) with watcher, listener and workers
looping normally.

## Known follow-up (not fixed this session)

The `nginx_reload` deploy step still fails inside the container with
`nsenter: reassociate to namespaces failed: Operation not permitted`. The
deployer treats it as optional, so it does not block a deploy, and the static
React bundle is served from the host checkout without a reload. Joining the
host mount namespace was attempted with `cap_add: SYS_ADMIN`, `pid: host`,
`privileged`, `seccomp=unconfined` and `apparmor=unconfined`; all returned
`EPERM`. A host-side reload trigger is needed before nginx configuration
changes can be rolled out by the daemon.

---

## Follow-ups

- Replace the in-container `nsenter` nginx reload with a host-side mechanism.
- Consider surfacing the orphaned-`Created` condition as a compose health signal;
  a partial recreate currently only shows up in `docker ps -a`.

## References

- Related: [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
- Related: [2026-11-12-scale-workers-without-recreate](/pages/2026-11-12-scale-workers-without-recreate.md)
