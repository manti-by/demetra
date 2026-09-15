---
title: Docker setup review — Dockerfile + docker-compose.yaml on mnt-164
date: 2026-08-17
type: code-review
status: resolved
session_id: "-"
services: [deploy, configs]
branch: mnt-164-docker-compose
tickets: [MNT-164]
tags: [docker, compose, security, review]
related: [2026-07-07-project-deploy-script.md, 2026-08-10-docker-compose-deploy.md, 2026-08-18-compose-anchors-refactor.md, 2026-08-19-worker-opencode-home-permissions.md]
---

# Docker setup review — Dockerfile + docker-compose.yaml on mnt-164

## TL;DR

Review of `mnt-164-docker-compose` found the previously-verified Docker setup regressed with multiple blockers preventing boot — missing source copy, stale venv path, `WORKDIR` typo, `.keys/` baked into image, dropped healthchecks, `DB_HOST` mismatch, `LOG_PATH` divergence, and wrong image tags. Findings 1–10,13–16 were fixed via subsequent commits; 11–12 were incorrect (see note).

> **Status update (2026-08-20):** Findings 1–10 and 13–16 fixed on `master` (see [[2026-08-18-compose-anchors-refactor]], [[2026-08-19-worker-opencode-home-permissions]]). 11–12 incorrect. This is a historical record; `docker compose up` on master is no longer blocked.

---

## Findings

### 1. App source not copied into image — Blocker

`Dockerfile` final stage removed `COPY . .` → every service fails `ModuleNotFoundError: No module named 'demetra'`. Fix: `COPY --chown=demetra:demetra . /srv/demetra/src/` with `.keys/` in `.dockerignore`.

### 2. `.keys/` baked into image — Security critical

`.keys/` in `.gitignore` but not `.dockerignore` → `COPY .keys/.ssh` etc. leaks SSH/GPG (`30F5AD2AA12FFE64`) via `docker pull`. Fix: add `.keys/` to `.dockerignore`, remove `COPY .keys` lines, mount at runtime.

### 3. Venv copied from non-existent path — Blocker

`Dockerfile:33` `COPY --from=builder /app/.venv` but builder `WORKDIR` is `/srv/demetra/src/` → venv at `/srv/demetra/src/.venv`. Build fails `not found`. Fix: both sides `/srv/demetra/src/.venv` (matches `ENV PATH`).

### 4. `WORKDIR /srv/app/src/` typo — Blocker

Should be `/srv/demetra/src/` (matches builder, `ENV PATH`, bind-mounts, `mkdir -p`). Fix one line.

### 5. Healthchecks removed — Blocker

`docker-compose.yaml:4-20` `postgres`/`redis` lost `pg_isready`/`redis-cli ping` → every `depends_on: condition: service_healthy` hard-errors. Restore healthchecks.

### 6. `watcher`/`listener` wrong `DB_HOST` — Blocker

DB renamed `db`→`postgres`; `docker-compose.yaml:95,117` still `DB_HOST: db` → crash-loop. Fix: `DB_HOST: postgres`.

### 7. Inconsistent `LOG_PATH` — High

`dictConfig(LOGGING)` runs at import (`runtime/tui.py:11`); non-existent parent → `ValueError`. Current mix: `api` ok (`/var/log/demetra/api.log`), `worker`/`listener` wrong (`/var/log/app/...`), `watcher` misleading. Fix: single convention `/var/log/demetra/<name>.log` or shared `/var/log/demetra/demetra.log`.

### 8. `image: demetra:latest` mismatch — Blocker

`docker-compose.yaml` uses `demetra:latest` but `Makefile` builds `mantiby/demetra:latest`; no `build:` in compose → `pull access denied`. Fix: `mantiby/demetra:latest` (or tag step).

### 9. `psycopg-binary` missing — Blocker

Pure `psycopg==3.3.4` + slim image (no libpq) → `migrate` `ImportError: no pq wrapper available` (previously fixed in [[2026-08-10-docker-compose-deploy]]). Fix: restore `psycopg-binary==3.3.4`, `uv lock`.

### 10. `react-build` bind-mount confusion — High

`docker-compose.yaml:149-156` `working_dir: /srv/demetra/src/` + `./react:/srv/demetra/src` collides with api bind-mount naming; misleading for `bun install && bun run build`. Fix: `/app` or `/build`.

### 11. `oven/bun:1` invalid tag — High (incorrect)

Claimed `oven/bun:1` not found — actually a valid major tag, still used. No fix needed.

### 12. API publish on all interfaces — Security (incorrect at review time, now valid)

Claimed `--host 0.0.0.0` + `8001:8001` exposes `/docs` etc. At review time publishes were loopback-only, so not exposed. **Superseded (2026-08-23):** current compose publishes `8001:8001`/`9181:9181` on all interfaces — concern reinstated, see [[2026-08-10-docker-compose-deploy]].

### 13. `.env.docker.example` stale `DB_HOST=db` — High

Template still `DB_HOST=db` while service is `postgres`; confusing, `watcher`/`listener` silently fail. Fix: `DB_HOST=postgres`.

### 14. `demetra_app_data` volume removed — Medium

Persisted `/root` (worktrees, UV venvs, session logs) gone → `down && up` wipes state while Postgres keeps dead paths. Fix: restore at `~/.demetra/projects`.

### 15. Sync URL driver — Informational

`database.py:97` sync URL `postgresql+psycopg://` vs async `asyncpg`; fine with `psycopg-binary`, fails on slim without. Resolved by #9.

### 16. `migrations` mount collision — Medium

`migrate` `./migrations:/srv/demetra/src/migrations:ro` vs api `./:/srv/demetra/src/` at same path — currently ok, flagged.

### 17. Version downgrade — Low

`pyproject.toml:3` `1.18.0`→`1.16.1` accidental. Fix: restore.

### 18. `wiki/INDEX.md` merge markers — Low

`<<<<<<< Updated upstream` around MNT-164 entry. Fix: resolve, keep [[2026-08-10-docker-compose-deploy]].

### 19. `docker-deploy` pull includes invalid tag — Low

`Makefile:121` `pull db redis react-build` depends on #11 fix.

### 20. `docker-run` legacy user — Low

`Makefile:99-100` hard-codes `manti`; new image user is `demetra`. Fix: `PARENT_HOME=/home/demetra/`.

---

## Summary table

| # | Severity | File(s) | Description |
|---|----------|---------|-------------|
| 1 | Blocker | `Dockerfile` | Source `COPY` missing |
| 2 | Security | `.dockerignore` | `.keys/` baked into image |
| 3 | Blocker | `Dockerfile:33/16` | Venv path mismatch |
| 4 | Blocker | `Dockerfile:48` | `WORKDIR` typo |
| 5 | Blocker | `compose:4-20` | Healthchecks missing |
| 6 | Blocker | `compose:95,117` | `DB_HOST: db` stale |
| 7 | High | `compose:53,75,97,119` | `LOG_PATH` mix |
| 8 | Blocker | `compose`/`Makefile` | Image tag mismatch |
| 9 | Blocker | `pyproject.toml` | `psycopg-binary` missing |
| 10 | High | `compose:149-156` | `react-build` paths |
| 11 | High | `compose:150` | `oven/bun:1` (actually valid) |
| 12 | Security | `compose:43,57` | `0.0.0.0` publish (loopback at review, now all-interfaces) |
| 13 | High | `.env.docker.example` | Stale `DB_HOST=db` |
| 14 | Medium | `compose:158` | Volume persistence removed |
| 15 | Info | `database.py:97` | Sync driver |
| 16 | Medium | `compose:30` | Mount collision |
| 17 | Low | `pyproject.toml:3` | Version downgrade |
| 18 | Low | `wiki/INDEX.md` | Merge markers |
| 19 | Low | `Makefile:121` | Pull tag |
| 20 | Low | `Makefile:99` | Legacy user |

7 Blocker · 5 High · 1 Security-critical · 1 Security · 3 Medium · 3 Low.

---

## Suggested fix order

1. #2 (.dockerignore) — stops credential leak.
2. #1,3,4 (Dockerfile) — unblocks all services.
3. #5,6,8,9 (compose healthchecks, DB_HOST, image, psycopg-binary) — unblocks migrate.
4. #7 (LOG_PATH) — unblocks import.
5. #10,11,12,13 (react-build, tag, publishes, template).
6. #14,16,17,18,19,20.

## Follow-ups

- Re-run `make docker-deploy` end-to-end after fixes.
- Consider `hadolint` in CI.

## Consistency note (2026-08-19)

Most fixed in anchor refactor — see [[2026-08-18-compose-anchors-refactor]]. #11 (`oven/bun:1`) valid; #12 was loopback-only at review, now all-interfaces again (2026-08-23).

## References

- Related: [[2026-08-10-docker-compose-deploy]], [[2026-07-07-project-deploy-script]], [[2026-08-18-compose-anchors-refactor]], [[2026-08-19-worker-opencode-home-permissions]]
- External: [MNT-164](https://linear.app/mnt/issue/MNT-164)
