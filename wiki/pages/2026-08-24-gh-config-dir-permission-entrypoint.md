---
title: gh config.yml permission denied in containers — un-gated entrypoint ownership repair
date: 2026-08-24
type: debug
status: resolved
session_id: build-agent-2026-08-24
services: [deploy, configs]
branch: "-"
tickets: [MNT-175]
tags: [docker, compose, permissions, volume, entrypoint, gh]
related: [2026-08-20-review-gh-auth-mount-changes.md, 2026-08-19-worker-opencode-home-permissions.md, 2026-08-18-compose-anchors-refactor.md]
---

# gh config.yml permission denied in containers — un-gated entrypoint ownership repair

## TL;DR

`gh auth` inside every container failed with `failed to write config after migration: open /home/demetra/.config/gh/config.yml: permission denied`. The `/home/demetra/.config/gh/` directory inside the `demetra_app_data` named volume was root-owned: Docker silently creates missing parent directories for file bind-mounts **as root**, and the entrypoint's ownership repair only ran once per volume behind the `.home-ready` marker — which predated the gh mount, so the new root-owned dir was never chowned. Fixed by pre-seeding both app config dirs demetra-owned in the image and repairing their ownership unconditionally on every boot; no manual cleanup needed on existing volumes.

---

## Symptom

User report on the compose deployment:

```text
gh auth doesn't work inside containers
failed to write config after migration: open /home/demetra/.config/gh/config.yml: permission denied
```

The message comes from `gh` itself: on startup it migrates its legacy config and writes `~/.config/gh/config.yml`, which requires write permission on the **directory** `.config/gh/`.

## Step 1 — Docker root-creates bind-mount parents inside the named volume

**File:** docker-compose.yaml:21

- `docker-compose.yaml` mounts the persistent named volume `demetra_app_data` at `/home/demetra/` and overlays file bind mounts onto it, including `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` (added in commit 48ef47d, MNT-175).
- When a file bind mount's parent path does not exist in the target, the Docker daemon `mkdir -p`s it **as root:root** inside the volume before attaching the mount. Same mechanism already documented for `auth.json` in [[2026-08-19-worker-opencode-home-permissions]].
- So `/home/demetra/.config/gh/` was born root-owned inside the volume.

## Step 2 — the ownership repair never saw the new directory

**File:** configs/docker-entrypoint.sh

- The entrypoint repairs home-volume ownership **once per volume**, gated on the `/home/demetra/.home-ready` marker created during the earlier opencode-EACCES fix.
- That marker was set by a boot *before* commit 48ef47d added the gh mount — so on every subsequent start the gated block is skipped and the root-owned `.config/gh/` survives forever.
- Containers run the app as `demetra` via `setpriv`; `gh` (and any process writing XDG config) gets EACCES creating files under `.config/gh/`.

This is the same failure class as [[2026-08-19-worker-opencode-home-permissions]], resurfacing through the marker short-circuit instead of a stale volume: **any new bind mount added after the marker is set lands with root-owned parents**.

## Root cause

Two gaps combined:

1. The image did not seed `~/.config/gh/` / `~/.local/share/opencode/`, so Docker had to root-create their parents when the file bind mounts appeared.
2. The per-volume `.home-ready` gate assumes the set of bind mounts is frozen — adding a new secret mount later produces root-owned dirs that no boot will ever repair.

## Resolution / Fix

**File:** configs/docker-entrypoint.sh:17

Unconditional (outside the `.home-ready` gate) `mkdir -p` + **non-recursive** `chown` of both app config dirs on every boot:

```sh
mkdir -p /home/demetra/.config/gh /home/demetra/.local/share/opencode
chown demetra:demetra /home/demetra/.config/gh /home/demetra/.local/share/opencode
```

Non-recursive deliberately: `hosts.yml` and `auth.json` inside those dirs are host-owned bind mounts and must keep host ownership (same reason they are pruned from the recursive find).

**File:** Dockerfile:35

Fresh volumes are seeded correctly so Docker never has to root-create parents:

```dockerfile
RUN useradd -m -s /bin/bash -d /home/demetra demetra \
    && mkdir -p /home/demetra/.config/gh /home/demetra/.local/share/opencode \
    && chown -R demetra:demetra /home/demetra
```

A named volume copies image content on first use, so these dirs exist demetra-owned before any bind mount is attached.

Redeploy path: `make docker-deploy` rebuilds the image; the per-boot repair fixes the existing `demetra_app_data` volume on next start — no manual `chown`. Safe with concurrent replicas (`deploy.replicas: 2`, scaled to 4): the repair is idempotent.

### Verification

- `sh -n configs/docker-entrypoint.sh` — OK.
- `docker compose config --quiet` — OK.

## Known follow-up

- Any **future** file bind mount under `/home/demetra/` whose parent dir is not pre-created in the image will hit this again (root-owned parents after the marker). Mitigation today covers only `.config/gh` and `.local/share/opencode`; add new parents to both the Dockerfile seed and the unconditional repair block when introducing a new secret mount.

## Update — 2026-08-24 16:02

`setpriv: initgroups failed: Operation not permitted` on `migrate-1` (and every other compose service) at container start, after commit `c6c0008` "Fix docker user" added `USER demetra` to the Dockerfile (and a later attempt to remove it was rejected — the operator wants everything running as `demetra`).

**Symptom:**

```text
migrate-1  | setpriv: initgroups failed: Operation not permitted
```

**Step 1 — `USER demetra` broke the root-only entrypoint path**

**File:** Dockerfile (commit `c6c0008`)

- `USER demetra` makes the container start as the unprivileged `demetra` (uid 1000) user, so the `ENTRYPOINT ["docker-entrypoint.sh"]` shell now runs as `demetra`, not root.
- Its final line `exec setpriv --reuid=demetra --regid=demetra --init-groups "$@"` therefore runs `setpriv` while already unprivileged. `--init-groups` calls `setgroups()`, which needs `CAP_SETGID` — an unprivileged user lacks it, so `setpriv` aborts with `initgroups failed: Operation not permitted` before the app command ever runs.
- The root-only ownership repair block (`.home-ready` gate + `mkdir`/`chown`) also became dead code: it needs root too.

**Root cause:** The entrypoint assumed it always starts as root (the `2026-08-19` design) and unconditionally executed `setpriv` + `chown`. Adding `USER demetra` inverted that assumption without the entrypoint knowing.

**Resolution / Fix — keep `USER demetra`, make the entrypoint user-aware**

**File:** configs/docker-entrypoint.sh

Guard the root-only work (ownership repair + `setpriv` drop) behind an `id -u` check, and otherwise just exec the command directly:

```sh
if [ "$(id -u)" = "0" ]; then
    # .home-ready gate + mkdir/chown repair (unchanged)
    exec setpriv --reuid=demetra --regid=demetra --init-groups "$@"
fi

exec "$@"
```

- As `demetra` (the normal compose path, `USER demetra`): the `if` is skipped and `exec "$@"` runs the app directly — no `setpriv`, no `chown`, no capabilities needed.
- As root (e.g. a one-off `docker run --user 0` repair): the ownership repair runs and drops to `demetra` via `setpriv`, preserving the documented self-heal path for fresh volumes.

**File:** Dockerfile

`USER demetra` restored/kept. No capability-granting change (`--cap-add`) is needed because the entrypoint no longer invokes `setpriv` on the demetra path.

### Verification

- `sh -n configs/docker-entrypoint.sh` — OK.
- The existing `demetra_app_data` volume is already demetra-owned, so the demetra path works as-is; rebuild and redeploy amon-ra with `make docker-deploy`.

## Follow-ups

- Redeploy amon-ra via `make docker-deploy` and confirm `gh api user -q .login` works inside a worker container.
- Confirm `migrate-1` starts clean (no `setpriv: initgroups failed`) after redeploy.

## References

- Related: [[2026-08-20-review-gh-auth-mount-changes]]
- Related: [[2026-08-19-worker-opencode-home-permissions]]
- Related: [[2026-08-18-compose-anchors-refactor]]
