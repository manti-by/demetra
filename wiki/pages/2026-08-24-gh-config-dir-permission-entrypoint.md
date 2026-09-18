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
related:
- 2026-08-19-worker-opencode-home-permissions.md
- 2026-08-20-review-gh-auth-mount-changes.md
- 2026-08-18-compose-anchors-refactor.md
---

# gh config.yml permission denied in containers — un-gated entrypoint ownership repair

## TL;DR

`gh auth` inside containers failed with `failed to write config after migration: open /home/demetra/.config/gh/config.yml: permission denied`. Docker creates missing bind-mount parent dirs as `root:root` inside the `demetra_app_data` volume, and the `.home-ready`-gated ownership repair (from the opencode fix) never ran again after the gh mount was added. Fixed by pre-seeding both config dirs demetra-owned in the image and repairing them unconditionally on every boot; later made the entrypoint user-aware when `USER demetra` was added to the Dockerfile.

## Symptom

`gh` migrates legacy config and writes `~/.config/gh/config.yml` — needs writable `.config/gh/` directory.

## Why

- `docker-compose.yaml:21` mounts `demetra_app_data` at `/home/demetra/` plus file bind mounts (`.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml`, added in `48ef47d` MNT-175). Docker `mkdir -p`s missing parents as `root:root` inside the volume (same as `auth.json` in [[2026-08-19-worker-opencode-home-permissions]]).
- `configs/docker-entrypoint.sh` repaired ownership only once (`.home-ready` marker from earlier fix). Marker predated gh mount → root-owned `.config/gh/` never repaired. App runs as `demetra` via `setpriv` → EACCES. Any new bind mount after marker suffers same fate.

## Root cause

1. Image did not seed `~/.config/gh/` / `~/.local/share/opencode/` so Docker root-created parents.
2. Per-volume `.home-ready` gate assumes frozen bind-mount set — new mounts land root-owned forever.

## Fix

`configs/docker-entrypoint.sh:17` — unconditional (outside gate) repair every boot (non-recursive to keep host-owned `hosts.yml`/`auth.json` intact):
```sh
mkdir -p /home/demetra/.config/gh /home/demetra/.local/share/opencode
chown demetra:demetra /home/demetra/.config/gh /home/demetra/.local/share/opencode
```

`Dockerfile:35` — seed fresh volumes demetra-owned so Docker never root-creates parents:
```dockerfile
RUN useradd -m -s /bin/bash -d /home/demetra demetra \
    && mkdir -p /home/demetra/.config/gh /home/demetra/.local/share/opencode \
    && chown -R demetra:demetra /home/demetra
```
Existing volume fixed on next boot via `make docker-deploy`; idempotent with 4 concurrent workers.

Verification: `sh -n configs/docker-entrypoint.sh` OK, `docker compose config --quiet` OK. Future mounts need same treatment (Dockerfile seed + unconditional repair).

## Update — 2026-08-24 16:02 — `setpriv: initgroups` failure

After `c6c0008` added `USER demetra` to Dockerfile, every service failed: `setpriv: initgroups failed: Operation not permitted`. Entrypoint assumed root start and unconditionally ran `setpriv --init-groups` + `chown` (needs `CAP_SETGID`). As `demetra` (uid 1000), `setgroups()` fails and repair is dead code.

**Fix** — `configs/docker-entrypoint.sh` — guard root-only work behind `id -u`:
```sh
if [ "$(id -u)" = "0" ]; then
    # .home-ready gate + mkdir/chown repair
    exec setpriv --reuid=demetra --regid=demetra --init-groups "$@"
fi
exec "$@"
```
As `demetra` (normal compose path): skip to `exec "$@"` — no `setpriv`/`chown` needed. As root (`docker run --user 0`): repair runs and drops via `setpriv`. `USER demetra` kept; no `--cap-add` needed. `sh -n` OK; existing volume already demetra-owned.

## Follow-ups

- Redeploy amon-ra via `make docker-deploy`; confirm `gh api user -q .login` inside worker and `migrate-1` starts clean.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-20-review-gh-auth-mount-changes]], [[2026-08-19-worker-opencode-home-permissions]], [[2026-08-18-compose-anchors-refactor]]
