---
title: Scaling RQ workers without recreating running containers
date: 2026-11-12
type: investigation
status: resolved
session_id: ses_e3017eff4ffe4Z3l3PlPgwbyhL
services: [deploy, configs, runtime, daemons]
branch: "-"
tickets: []
tags: [docker, compose, workers, scale, no-recreate, operations, rq]
related: [2026-08-10-docker-compose-deploy.md, 2026-08-18-compose-anchors-refactor.md]
---

# Scaling RQ workers without recreating running containers

## TL;DR

Yes — `docker compose up -d --scale worker=4 --no-recreate worker` adds two worker
containers and leaves the running ones untouched. Verified live on 2026-11-12: the stack went
from 2 to 4 workers, `demetra-worker-1`/`worker-2` kept their original start times and image,
and only `worker-3`/`worker-4` were created. Both new workers registered themselves in RQ and
one picked up a job within seconds.

---

## Net effect

- **Capacity only, no downtime.** The two pre-existing workers were never stopped, recreated or
  restarted — their `StartedAt` and image ID are unchanged, so any workflow job they were
  executing survived the scale-up untouched.
- **The scale-up is not durable.** `make deploy` (`Makefile:31`) brings the stack up with
  `--scale worker=2 --force-recreate`, so the next deploy silently drops back to 2 workers and
  bounces every container. The 4-worker state only survives as long as no deploy runs, even
  though the compose file was bumped to `deploy.replicas: 4` in the working tree.
- **`--no-recreate` is a double-edged flag.** It is what keeps the running workers alive, but it
  also means they never pick up a new image or a changed service definition. A rebuilt
  `mantiby/demetra:latest` reaches only the newly created containers.

---

## The worker service

**File:** `docker-compose.yaml:110-117`

```yaml
  worker:
    <<: *demetra-app
    command: ["python", "-m", "demetra.worker"]
    environment:
      <<: *demetra-env
      LOG_PATH: /var/log/demetra/worker.log
    deploy:
      replicas: 4
```

Points that matter for scaling:

- `deploy.replicas` is only a default — an explicit `--scale worker=N` on the command line
  overrides it. The compose file never has to change to run more workers.
- The committed value is still `2`; the working tree was bumped to `4` on 2026-11-12 (right
  after this session's scale-up, uncommitted at the time of writing). `deploy.replicas` only
  applies to `docker compose up` runs that do **not** pass `--scale`, so the bump alone does not
  change a running stack.
- The service deliberately sets **no** `container_name` (unlike `postgres`/`redis`, which do).
  Compose derives the container names from the service name and an index (`demetra-worker-3`),
  which is exactly what makes `--scale` possible.
- `depends_on` (`docker-compose.yaml:38-44`) gates the service on `migrate` finishing
  successfully plus healthy `postgres`/`redis`.

**File:** `demetra/worker.py:12-13`

```python
        worker = Worker(["default"], connection=connection)
        worker.work()
```

A plain RQ worker on the shared `default` queue (`demetra/services/persistence/queue.py:9`
sets `default_timeout=SUBPROCESS_TIMEOUT + 60`). RQ's work-horse/registry model means a worker
that starts later simply registers itself and work-steals from the same Redis queue — no queue
restart, no job duplication, no re-enqueue of in-flight jobs. That is why adding capacity is
safe while workflows are running.

---

## The command

```bash
docker compose --env-file .env.docker up -d --scale worker=4 --no-recreate worker
```

- `--scale worker=4` — the CLI flag wins over `deploy.replicas: 2`.
- `--no-recreate` — Compose does not recreate containers whose configuration changed; it only
  creates the missing instances. Without it, Compose would recreate any container whose config
  hash moved (e.g. after a rebuild), which is precisely what the request was to avoid.
- Targeting only the `worker` service keeps the rest of the stack (api, watcher, listener,
  rq-dashboard) out of the operation.

Dry run first, to see the plan without touching anything:

```bash
docker compose --env-file .env.docker up -d --scale worker=4 --no-recreate --dry-run worker
```

which printed `Container demetra-worker-1 Running` / `demetra-worker-2 Running` (untouched)
alongside `demetra-worker-3 Creating` / `demetra-worker-4 Creating`.

---

## Verification

State before the change:

- `demetra-worker-1` — up 3 hours, image `sha256:211a3dc…`
- `demetra-worker-2` — up 3 hours, image `sha256:211a3dc…`

State after the change (`docker compose ps`, `docker inspect`):

- `demetra-worker-1` — up 4 hours, `StartedAt=2026-11-12T09:48:53Z`, image `sha256:211a3dc…` — unchanged
- `demetra-worker-2` — up 4 hours, `StartedAt=2026-11-12T09:48:53Z`, image `sha256:211a3dc…` — unchanged
- `demetra-worker-3` — up 3 minutes, `StartedAt=2026-11-12T13:18:31Z`, image `sha256:211a3dc…` — new
- `demetra-worker-4` — up 3 minutes, `StartedAt=2026-11-12T13:18:31Z`, image `sha256:211a3dc…` — new

Further checks:

- All four workers report the **same** image ID as `mantiby/demetra:latest`
  (`sha256:211a3dc…`, built 2026-10-10), so the "old image on the old workers" caveat did not
  bite in this instance.
- RQ registry `rq:workers` holds 4 worker keys — the new containers announced themselves.
- `docker logs demetra-worker-3` shows it immediately picked up a `plan-agent` job, i.e. the
  extra capacity was consumed, not idle.
- Compose version in use: `v5.6.1`.

---

## Caveats

- **The `migrate` one-shot still runs.** `depends_on: migrate: service_completed_successfully`
  means Compose starts `migrate` (an `alembic upgrade head` one-shot) before the workers. At
  the current revision it is a no-op, but it does touch the database and is worth knowing about
  before running this on a schedule.
- **Old image stays on old workers.** Because `--no-recreate` suppresses recreation, a container
  started before a rebuild keeps running the previous image. Compare with
  `docker inspect -f '{{.Image}}' demetra-worker-1` vs
  `docker image inspect mantiby/demetra:latest -f '{{.Id}}'` to detect drift.
- **Scaling down is not implied.** `--scale worker=4` never removes surplus containers on its
  own; the count only shrinks when Compose recreates the service (e.g. `make deploy`).

---

## Make targets disagree with the live count

> **Resolved (2026-11-14, commit `1a53faf` "Upscale workers, templates, minor fixes"):** the
> `deploy` target was updated to `--scale worker=4` (and now includes `deployer`), so both
> Make targets and the compose file's `deploy.replicas: 4` agree; the canonical worker count
> is **4**. The historical `worker=2` quotes below describe the pre-`1a53faf` state.

**File:** `Makefile:26-32` (`deploy`)

```make
deploy:
	git pull --ff-only
	docker build --platform linux/amd64 --tag mantiby/demetra:latest .
	…
	docker compose --env-file .env.docker up --detach --force-recreate --scale worker=2 api worker watcher listener rq-dashboard
```

**File:** `Makefile:100-101` (`docker-up`)

```make
docker-up:
	docker compose --env-file .env.docker up -d --scale worker=4 api worker watcher listener rq-dashboard
```

So the repo carries two different worker counts, and neither matches "scale up live without
restarting":

- `make deploy` — `--scale worker=2` **plus** `--force-recreate`: bounces every container of every
  service and drops back to 2 workers, even though the compose file now says
  `deploy.replicas: 4` (the CLI `--scale` flag wins over the file).
- `make docker-up` — `--scale worker=4` but **without** `--no-recreate`: gets the count right
  but may still recreate workers whose configuration changed.

Neither is the operation that was needed here. The live, non-disruptive path is the raw
`docker compose up -d --scale worker=4 --no-recreate worker` command above; it is currently not
wrapped in a Make target.

---

## Open questions

- Should the deploy path adopt `--scale worker=4` to match `docker-up` and the compose file's
  `deploy.replicas: 4`, and should the `--force-recreate` in `Makefile:31` be narrowed to the
  services that actually need it?
- Should the "scale up without bouncing" command become a Make target (e.g.
  `make docker-scale-workers N=4`) so operators do not have to remember the flags?
- Is there value in a drift check that compares the running containers' image IDs against
  `mantiby/demetra:latest` and warns when `--no-recreate` has left stale workers behind?

---

## Follow-ups

- ~~Decide the canonical worker count (2 or 4) and align `Makefile:31` and `Makefile:101` with it.~~ **Done 2026-11-14** (`1a53faf`) — canonical count is 4; both targets aligned.
- Consider adding a `make docker-scale-workers` target wrapping the verified command.

## References

- Related: [[2026-08-10-docker-compose-deploy]], [[2026-08-18-compose-anchors-refactor]]
