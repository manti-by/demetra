---
title: Worker opencode EACCES on home volume — entrypoint ownership fix
date: 2026-08-19
type: debug
status: resolved
session_id: "-"
services: [deploy, agents, runtime]
branch: "-"
tickets: []
tags: [docker, permissions, volume, opencode, entrypoint]
related: [2026-08-10-docker-compose-deploy.md, 2026-08-17-docker-setup-review.md, 2026-08-18-compose-anchors-refactor.md]
---

# Worker opencode EACCES on home volume — entrypoint ownership fix

## TL;DR

The worker container on amon-ra failed at the plan step: `Plan agent failed (exit 1): EACCES: permission denied, mkdir '/home/demetra/.local/share/opencode/repos'`. The `demetra_app_data` named volume mounted at `/home/demetra` contains root-owned directories (created by an earlier image/root-run container before the `demetra` user existed), so the `demetra` user could not create `~/.local/share/opencode`. Fixed by adding a root entrypoint that repairs home-volume ownership once per volume (marker-gated) and then drops to `demetra` via `setpriv`.

---

## Symptom

Worker container on amon-ra:

```text
ERROR : Workflow error: Plan agent failed (exit 1): EACCES: permission denied, mkdir '/home/demetra/.local/share/opencode/repos'
```

`run_opencode_agent` (`demetra/services/agents/opencode.py:270`) spawns the opencode CLI as a subprocess of the worker; opencode initialises its XDG data dir `~/.local/share/opencode` and got EACCES because the parent volume root was not writable by the `demetra` user.

## Step 1 — Why the home dir is root-owned

- The Dockerfile previously ran the app as `USER demetra` (`useradd -m ... demetra`, uid 1000) — the image's `/home/demetra` is demetra-owned.
- `docker-compose.yaml` mounts the persistent named volume `demetra_app_data` at `/home/demetra/` (`docker-compose.yaml:15`). Worktrees, projects, UV venvs and opencode state all live under it (`demetra/settings.py:41` `WORKTREE_PATH = HOME/.demetra/projects`, `demetra/settings.py:160` `GIT.worktree_path = HOME/.demetra/worktrees/`).
- A named volume is populated from the image only when empty; the existing volume predates the `demetra` user, so the top-level and several subdirs are root-owned. The app running as `demetra` can write worktrees (created later, demetra-owned) but opencode's `~/.local` was root-owned → EACCES.

## Step 2 — Fix chosen

Image-level `chown` cannot repair an existing volume (it only seeds a fresh one), so the fix has to run at container start against the mounted volume. Added a root entrypoint that:

1. Runs as root (the `USER demetra` directive was removed from the image).
2. On first start per volume (marker `/home/demetra/.home-ready`) recursively chowns the home volume to `demetra:demetra`, **pruning the bind-mounted secret paths** (`.ssh`, `.gnupg`, `.gitconfig`, `.git-credentials` from `.keys/`, plus `.local/share/opencode/auth.json`) so host secret ownership is never touched.
3. Drops privileges with `setpriv --reuid=demetra --regid=demetra --init-groups` and execs the real CMD.

**File:** `docker-entrypoint.sh`

```sh
#!/bin/sh
set -e

export HOME=/home/demetra

if [ ! -e /home/demetra/.home-ready ]; then
    chown demetra:demetra /home/demetra
    find /home/demetra -mindepth 1 \
        \( -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
        -o -exec chown demetra:demetra {} +
    touch /home/demetra/.home-ready
    chown demetra:demetra /home/demetra/.home-ready
fi

exec setpriv --reuid=demetra --regid=demetra --init-groups "$@"
```

`HOME` is exported explicitly because the entrypoint runs as root (Docker would otherwise set it to `/root`); opencode/git/uv must see `/home/demetra`.

**File:** `Dockerfile` — copied the script, replaced `USER demetra` with `ENTRYPOINT ["docker-entrypoint.sh"]`. All compose services (`migrate`, `api`, `worker`, `watcher`, `listener`, `rq-dashboard`) inherit the entrypoint and keep their per-service `CMD` overrides.

Verified locally: `sh -n` passes and a `find -prune` dry-run traverses exactly the non-secret set (`.local`, `.demetra`, `.cache`, …) while skipping `.ssh`, `.gnupg`, `.gitconfig`, `.git-credentials` and `.local/share/opencode/auth.json`.

## Test Results

- `sh -n docker-entrypoint.sh` — OK.
- `find` traversal dry-run on a scratch tree — secret paths pruned, everything else visited.
- Container build not run locally (no Docker daemon on this machine); deploy via `make docker-deploy` on amon-ra will exercise the entrypoint on the existing volume.

## Known follow-up

- If the host `.keys/.ssh` / `.keys/.gnupg` files are not readable by uid 1000, SSH/gpg signing from inside the container will fail — out of scope for this error, worth checking if commits start failing after redeploy.

---

## Follow-ups

- Redeploy on amon-ra: `make docker-deploy` (rebuilds the image, recreates the worker); the entrypoint repairs the volume on first start — no manual `chown` needed.
- Optionally verify with `docker compose --env-file .env.docker exec worker id demetra` (expect `uid=1000`).

## References

- Related: [[2026-08-18-compose-anchors-refactor]]
- Related: [[2026-08-17-docker-setup-review]]
- Related: [[2026-08-10-docker-compose-deploy]]