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

The in-progress `mnt-164-docker-compose` branch has regressed the previously-verified Docker setup in [[2026-08-10-docker-compose-deploy]] and introduced **multiple critical blockers** that prevent any container from booting. The most damaging: the final-stage `Dockerfile` no longer copies the application source, the venv is `COPY`ed from a path that no longer exists in the builder, `WORKDIR` is a typo (`/srv/app/src/`), and the host's `.keys/` (SSH + GPG + git credentials) is baked into every image layer because `.keys/` is in `.gitignore` but **not** in `.dockerignore`. The compose file also drops all healthchecks, renames the DB service to `postgres` while leaving `watcher` and `listener` pointing at the old name `db`, and ships an inconsistent mix of `LOG_PATH` values whose parents don't exist. Until these are fixed, `docker compose up` will fail before `alembic` runs.

> **Status update (2026-08-20, Consistency Agent):** Findings 1–10 and 13–16 were fixed on
> `master` via subsequent commits (Dockerfile restore, compose anchor refactor, entrypoint fix —
> see [[2026-08-18-compose-anchors-refactor]] and [[2026-08-19-worker-opencode-home-permissions]]).
> Findings 11–12 were incorrect (see the consistency note below). This page is a historical
> code-review record of the mnt-164 branch state on 2026-08-17; current `docker compose up` on
> master is no longer blocked by these issues.

---

## Findings

Findings are ordered by severity. Each entry names the file and the symptom; "Fix" is the smallest change that resolves it without redesigning the stack.

### 1. Application source code is not copied into the image

**File:** `Dockerfile:49-...` (final stage) — `COPY . .` was removed from the final stage; the builder's `pyproject.toml`/`uv.lock` are the only source files in the build.

**Severity:** Blocker — no app service can start.

**Problem:** `uvicorn demetra.app:app`, `python -m demetra.worker`, `python -m demetra.watcher`, `python -m demetra.listener`, `alembic` all need the project source on disk in the final image. The build stages no longer copy it, so every long-running service and the `migrate` one-shot will fail with `ModuleNotFoundError: No module named 'demetra'` (or `can't open file 'main.py'` for the CMD).

**Fix:** Re-add `COPY --chown=demetra:demetra . /srv/demetra/src/` (or equivalent) in the final stage after the venv is in place, with `.keys/` excluded via `.dockerignore` (see Finding 2).

### 2. `.keys/` (SSH + GPG + git credentials) baked into the image

**File:** `.dockerignore` (missing entry); `Dockerfile:38-41`

**Severity:** Security critical.

**Problem:** `.keys/` is in `.gitignore` (so the contents are local-only), but it is **not** in `.dockerignore`. The Dockerfile `COPY --chown=demetra:demetra .keys/.ssh /home/demetra/.ssh` (and the `.gnupg`, `.gitconfig`, `.git-credentials` lines) will be sent through the build context and baked into the image layers — even on a public registry. The local `.keys/.gitconfig` references the real GPG signing key `30F5AD2AA12FFE64` (matches `DEMETRA_SIGNIN_KEY_ID` in `.env`). Anyone with `docker pull` access gets the keys.

**Fix:** Add `.keys/` to `.dockerignore` (and arguably `**/.keys/`). After that, the four `COPY --chown=demetra:demetra .keys/...` lines in the final stage should be removed; credentials should be mounted at runtime (`-v` / compose volumes / Docker secrets), not baked. Until then, the `chmod 700` on the destination and the `--chown` do nothing to mitigate exfiltration via the image.

### 3. venv is `COPY`ed from a path that no longer exists in the builder

**File:** `Dockerfile:33` (`COPY --from=builder /app/.venv /app/.venv`) vs. `Dockerfile:16` (`WORKDIR /srv/demetra/src/`)

**Severity:** Blocker — even if Finding 1 is fixed, every command on `PATH` resolves to nothing.

**Problem:** The builder stage was reworked to `WORKDIR /srv/demetra/src/`, so `uv sync --frozen` installs the venv at `/srv/demetra/src/.venv` (uv's default is `<cwd>/.venv`). The final stage then `COPY`s from `/app/.venv`, which does not exist in the builder — `docker build` will fail the `COPY` with `ERROR: failed to solve: failed to compute cache key: "/app/.venv": not found`. (On a `COPY --from=...` of a missing path, the build fails outright, not silently.)

**Fix:** Change both source and destination to `/srv/demetra/src/.venv` (or move the `WORKDIR` back to `/app` in the builder and `uv sync --frozen --no-dev --no-cache` as before). The `ENV PATH="/srv/demetra/src/.venv/bin:$PATH"` line already matches the `/srv/demetra/src/...` layout, which suggests the layout was intended but the `COPY` was left stale.

### 4. `WORKDIR /srv/app/src/` typo in the final stage

**File:** `Dockerfile:48`

**Severity:** Blocker.

**Problem:** The intended WORKDIR is `/srv/demetra/src/` (matches the builder WORKDIR, the venv layout, the `ENV PATH`, the bind-mount paths in compose, and the existing `mkdir -p /srv/demetra/src/` two lines above). The final image sets `WORKDIR /srv/app/src/`, which (a) does not exist (no parent was created), and (b) the `CMD ["python", "main.py", "--help"]` therefore resolves against a non-existent directory.

**Fix:** `WORKDIR /srv/demetra/src/`.

### 5. Healthchecks removed — `depends_on: condition: service_healthy` will fail

**File:** `docker-compose.yaml:4-20` (postgres + redis blocks)

**Severity:** Blocker — every other service depends on this.

**Problem:** The verified `2026-08-10` compose had `pg_isready` and `redis-cli ping` healthchecks on `db`/`redis`. The current compose drops both healthcheck blocks. Every `depends_on: postgres: condition: service_healthy` / `depends_on: redis: condition: service_healthy` gate (used by `migrate`, `api`, `worker`, `watcher`, `listener`, `rq-dashboard`) is now a hard error: `service "postgres" has no healthcheck declared`.

**Fix:** Restore the healthchecks. Minimum:

```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
    interval: 5s
    timeout: 5s
    retries: 12
    start_period: 10s
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 10
```

### 6. `watcher` and `listener` still point at the old `db` hostname

**File:** `docker-compose.yaml:95,117`

**Severity:** Blocker for those two services.

**Problem:** The DB service was renamed `db` → `postgres` (and the volume is `demetra_postgres_data`). `migrate`, `api`, and `worker` correctly override `DB_HOST: postgres` in `environment:`. `watcher` and `listener` still set `DB_HOST: db`, which no longer exists — both daemons will fail to connect and crash-loop on `DatabaseError`.

**Fix:** Change `DB_HOST: db` → `DB_HOST: postgres` in both the `watcher` and `listener` blocks (and also in the example `.env.docker.example:11` if the template is shipped).

### 7. Inconsistent / non-existent `LOG_PATH` values

**File:** `docker-compose.yaml:53,75,97,119`

**Severity:** High — the app's `logging.config.dictConfig(LOGGING)` runs at module import (`demetra/services/runtime/tui.py:11`, `watcher.py:10`, `listener.py:19`) and crashes on `ValueError: Unable to configure handler 'file'` if the parent directory is not writable.

**Problem:** The four app services each override `LOG_PATH` differently:

| Service     | LOG_PATH override                  | Issue                                                                                |
|-------------|------------------------------------|--------------------------------------------------------------------------------------|
| `api`       | `/var/log/demetra/api.log`         | OK — parent is bind-mounted in the same block.                                       |
| `worker`    | `/var/log/app/worker.log`          | Wrong — `/var/log/app` is not created and not in the bind mount (`/var/log/demetra`).|
| `watcher`   | `/var/log/demetra/worker.log`      | Misleading name (it's the watcher's log, not the worker's) and inconsistent.         |
| `listener`  | `/var/log/app/listener.log`        | Same wrong `/var/log/app` prefix as the worker.                                      |

The bind mount `- /mnt/data/www/demetra/log/:/var/log/demetra/` only provides `/var/log/demetra/`, so `worker` and `listener` will crash on import.

**Fix:** Pick a single convention and apply it everywhere. Two clean options:

1. Mirror the verified setup: drop the per-service `LOG_PATH` overrides and let `.env.docker` provide `LOG_PATH=/var/log/demetra/demetra.log` (one file, parent already bind-mounted). All four services write to the same rolling log, separated by logger name. (This is the pre-existing pattern and the one the wiki documents.)
2. Or per-service files: set all four to `/var/log/demetra/<name>.log` and `mkdir -p` it explicitly; drop the `/var/log/app/...` typo on `worker`/`listener`.

### 8. `image: demetra:latest` doesn't match the build target

**File:** `docker-compose.yaml:23,36,68,90,112,134` (every app service); `Makefile:94` (`docker-build`)

**Severity:** Blocker — `docker compose up` will fail with `pull access denied for demetra` or `image not found`.

**Problem:** The compose file references `image: demetra:latest` for `migrate`, `api`, `worker`, `watcher`, `listener`, `rq-dashboard`. The `Makefile` `docker-build` target tags the image `mantiby/demetra:latest`. Nothing in the repo produces a `demetra:latest` tag, and there is no `build:` section in compose (which is the only override Compose would consult).

**Fix:** Either
- Change every `image: demetra:latest` → `image: mantiby/demetra:latest` (and document `${DEMETRA_IMAGE:-mantiby/demetra:latest}` in the example env, as the verified compose did), **or**
- Add a `docker tag mantiby/demetra:latest demetra:latest` step in `docker-deploy` (and a corresponding `docker tag` in the docs / `Makefile`).

The first option matches the existing build pipeline and the wiki-documented behaviour.

### 9. `psycopg-binary` missing → `migrate` will fail with `ImportError: no pq wrapper available`

**File:** `pyproject.toml:18-19` (around `psycopg`); `migrate` service in compose

**Severity:** Blocker for `migrate`.

**Problem:** `psycopg==3.3.4` is declared pure; the slim base image has no `libpq` system package, and `psycopg-binary` is not in the dependency list. The verified setup in [[2026-08-10-docker-compose-deploy]] Step 4 already documents this as a previously-fixed issue — it appears the bump/cleanup reverted the `psycopg-binary` line.

**Fix:** Re-add `psycopg-binary==3.3.4` (or `>=3.3.4,<4`) to the `[project] dependencies` list in `pyproject.toml`; rerun `uv lock` and rebuild.

### 10. `react-build` bind-mount is mounted at the same path as the `working_dir` in the wrong place

**File:** `docker-compose.yaml:149-156`

**Severity:** High — React build will fail or build the wrong tree.

**Problem:**

```yaml
react-build:
  image: oven/bun:1
  working_dir: /srv/demetra/src/   # <-- typo or copy/paste from a service that had a repo workdir
  command: ["sh", "-c", "bun install --frozen-lockfile && bun run build"]
  volumes:
    - ./react:/srv/demetra/src     # <-- mounts the react/ subtree to the WORKDIR
    - demetra_react_dist:/app/dist
```

The volume `./react:/srv/demetra/src` mounts the host's `react/` subdirectory on `/srv/demetra/src` inside the container. Combined with `working_dir: /srv/demetra/src/`, `bun install` will run inside the React subtree — which is correct for the install, but then `bun run build` will try to read `vite.config.*`, `package.json`, etc. from the **mounted** path, which is the host's `react/` (a single project, not the whole repo). This is fine in isolation, but the `working_dir: /srv/demetra/src/` is misleading (suggests the whole repo when only `react/` is available) and the mount target naming collides with the api/worker/watcher/listener bind-mount target (`/srv/demetra/src/`), which is also in the image. Use `/app` or `/build` to disambiguate.

**Fix:** Either

```yaml
react-build:
  working_dir: /build
  volumes:
    - ./react:/build
    - demetra_react_dist:/app/dist
```

or keep the verified setup: `working_dir: /app` and `./react:/app`.

### 11. `bun:1` is a non-existent major tag

**File:** `docker-compose.yaml:150`

**Severity:** High — `docker pull` fails.

**Problem:** `oven/bun:1` is not a valid tag on Docker Hub. The current valid tags are `oven/bun:1.1`, `oven/bun:1.2`, etc. Compose / Docker will return `manifest for oven/bun:1 not found`.

**Fix:** Pin a specific version, e.g. `oven/bun:1.2` or `oven/bun:1.1`. Better, pin the digest for reproducibility.

### 12. API binds `0.0.0.0` and publishes on all interfaces

**File:** `docker-compose.yaml:43,57-58`

**Severity:** Security regression vs. [[2026-08-10-docker-compose-deploy]].

**Problem:** `command: uvicorn ... --host 0.0.0.0` and `ports: - "8001:8001"` together expose the FastAPI app (`/docs`, `/users/me/env`, webhook receivers) on every host interface. The verified setup bound `127.0.0.1:8001:8001` so the host's nginx is the sole ingress (and TLS terminator). The same applies to `rq-dashboard:9181` (no auth, lets anyone browse/cancel jobs).

**Fix:**

```yaml
api:
  command:
    ["uvicorn", "demetra.app:app", "--host", "127.0.0.1", "--port", "8001", "--workers", "4"]
  ports:
    - "127.0.0.1:8001:8001"
...
rq-dashboard:
  command: ["rq-dashboard", "--redis-url", "redis://redis:6379/1", "--port", "9181"]
  ports:
    - "127.0.0.1:9181:9181"
```

(`rq-dashboard` 0.9.0 has no `--host` flag; the default bind is fine — only the publish-side needs the loopback fix.)

### 13. `parity` of `.env.docker` template vs. actual service name

**File:** `.env.docker.example:11,12,14` (still say `db`); `docker-compose.yaml:5-13` (service is now `postgres`)

**Severity:** High — operator footgun.

**Problem:** `.env.docker.example` sets `DB_HOST=db`, `DB_USER=demetra`, `DB_NAME=demetra` (matching the legacy service name). With the new compose the service is `postgres`; the app's `environment:` overrides `DB_HOST: postgres` on `migrate`/`api`/`worker` (but **not** on `watcher`/`listener`, see Finding 6), and the `POSTGRES_*` vars for the `postgres` service itself use the in-block `environment:` list (`POSTGRES_DB=demetra`, etc.). The template's `DB_HOST=db` is overridden for most services by the compose `environment:`, but the inconsistency makes the template confusing and the failure mode on `watcher`/`listener` is silent.

**Fix:** Update `.env.docker.example` to use `DB_HOST=postgres` (and add a one-line comment that the compose `environment:` overrides it on each app service).

### 14. `demetra_app_data` volume is gone — worktrees / projects / per-project UV venvs are not persisted

**File:** `docker-compose.yaml:158-163` (volumes list)

**Severity:** Medium.

**Problem:** The verified setup persisted `/root` (worktrees, projects, per-project UV venvs from MNT-161, session logs, copied auth) in `demetra_app_data`. The new compose only bind-mounts `./:/srv/demetra/src/` (code) and `/mnt/data/www/demetra/log/:/var/log/demetra/` (logs). Any `docker compose down && up` (or image rebuild) wipes worktrees, projects, and per-project venvs. Postgres keeps rows pointing at dead `local_path`s.

**Fix:** Either restore `demetra_app_data` mounted at the location the app uses for `WORKTREE_PATH` (`demetra/settings.py:39`, default `~/.demetra/projects/`, which is `/home/demetra/.demetra/projects` for the new `demetra` user) — or accept the loss and document the `down -v` step as destructive.

### 15. `psycopg-binary` / `psycopg` URL driver confusion

**File:** `demetra/services/persistence/database.py:97` (`url = f"postgresql+psycopg://..."`)

**Severity:** Informational.

**Problem:** The async URL uses `asyncpg` (line 47), but the sync URL used by alembic uses `postgresql+psycopg://` (line 97). With `psycopg-binary` available, both are fine. With pure `psycopg` (no `-binary`) on a slim image, the sync path fails while the async path still works. Worth pinning the sync driver to `postgresql+psycopg-binary://` for safety, or keeping `psycopg-binary` (per Finding 9) in the image.

**Fix:** Add `psycopg-binary` to the dependency list (per Finding 9); no code change needed.

### 16. `migrations` mount path is now in the bind-mount collision zone

**File:** `docker-compose.yaml:30` (`./migrations:/srv/demetra/src/migrations:ro`)

**Severity:** Medium.

**Problem:** The `migrate` service bind-mounts `./migrations` on `/srv/demetra/src/migrations`. The `api`/`worker`/`watcher`/`listener` services bind-mount the whole repo `./:/srv/demetra/src/`. The mount targets are the same path. If the api/worker services share a `demetra_app_data` style volume on `/srv/demetra/src/`, the two mounts will fight. With the current `WORKDIR /srv/demetra/src/` and the only bind-mount being the whole repo, the migration files end up correctly under `migrations/`, but only because the api/worker bind-mounts do **not** exist in the current compose. (This is a pre-existing fragility in the verified design, but the new compose has it cleaner.) Leave as-is.

**Fix:** None needed; flagged for awareness.

### 17. Version downgrade in `pyproject.toml`

**File:** `pyproject.toml:3` (uncommitted diff: `1.18.0` → `1.16.1`)

**Severity:** Low.

**Problem:** The working tree shows `version = "1.16.1"` while the previous committed value on this branch was `1.18.0`. This is a downgrade and the index entry `MNT-164: Docker compose` on 2026-08-10 describes the change as part of the MNT-164 feature work. Probably an accidental reset.

**Fix:** Re-set to `1.18.0` (or whichever post-MNT-161 value is current on the base branch) and rerun `uv lock` if any deps changed.

### 18. `wiki/INDEX.md` has unresolved merge-conflict markers

**File:** `wiki/INDEX.md:10-14`

**Severity:** Low — but blocks any future wiki automation / `Consistency Agent`.

**Problem:** The uncommitted `wiki/INDEX.md` change on this branch contains `<<<<<<< Updated upstream` / `=======` / `>>>>>>> Stashed changes` markers around the MNT-164 entry. The page `2026-08-10-mnt-164-docker-compose.md` was added (auto-generated by a build plan) and the index is mid-merge.

**Fix:** Resolve the conflict (keep the canonical reference [[2026-08-10-docker-compose-deploy]]). The auto-generated `2026-08-10-mnt-164-docker-compose.md` page was a stub and has since been deleted as part of the wiki dedup (its session note merged into the canonical page).

### 19. `oven/bun:1` is not pulled by the `docker-deploy` target's `pull` step

**File:** `Makefile:121` (`docker compose ... pull db redis react-build`)

**Severity:** Low (no-op because of Finding 11 — but if 11 is fixed, this works).

**Problem:** The deploy script pulls `db`, `redis`, `react-build`. The `react-build` service uses `oven/bun:1`, which is invalid (Finding 11). If the tag is corrected, this `pull` line correctly pre-fetches it.

**Fix:** Resolved by Finding 11.

### 20. `docker-run` Makefile target still assumes the legacy `manti` user

**File:** `Makefile:99-100`

**Severity:** Low (out of scope for MNT-164, but worth noting).

**Problem:** `docker-run` uses `-e PARENT_HOME=/home/manti/ -v "$(HOME):/home/manti/:ro"`, which references the user `manti` from the old image. The new image creates a `demetra` user. Running `make docker-run` after a rebuild will hit "user not found" errors when the app tries to read the parent home.

**Fix:** Update the target to mirror the verified compose: `PARENT_HOME=/home/demetra/` and `-v "$(HOME):/home/demetra:ro"`.

---

## Summary table

| #  | Severity   | File(s)                                                          | Description                                                                                                  |
|----|------------|------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------|
| 1  | Blocker    | `Dockerfile` (final stage)                                       | App source `COPY . .` is missing; no service can start.                                                      |
| 2  | Security   | `.dockerignore`, `Dockerfile:38-41`                              | `.keys/` (SSH + GPG + git credentials) is baked into the image — `.dockerignore` is missing the entry.       |
| 3  | Blocker    | `Dockerfile:33` vs. `Dockerfile:16`                              | venv copied from `/app/.venv` in builder, but builder `WORKDIR` is `/srv/demetra/src/`.                       |
| 4  | Blocker    | `Dockerfile:48`                                                  | `WORKDIR /srv/app/src/` typo — should be `/srv/demetra/src/`.                                                |
| 5  | Blocker    | `docker-compose.yaml:4-20`                                       | `postgres` + `redis` have no healthchecks; `depends_on: condition: service_healthy` will fail.                |
| 6  | Blocker    | `docker-compose.yaml:95,117`                                     | `watcher` + `listener` set `DB_HOST: db` but service is `postgres`.                                          |
| 7  | High       | `docker-compose.yaml:53,75,97,119`                               | `LOG_PATH` overrides mix `/var/log/demetra/...` and non-existent `/var/log/app/...`; import will crash.       |
| 8  | Blocker    | `docker-compose.yaml:23,36,68,90,112,134`; `Makefile:94`          | `image: demetra:latest` but `make docker-build` tags `mantiby/demetra:latest`.                               |
| 9  | Blocker    | `pyproject.toml` (deps); `migrate` service                       | `psycopg-binary` missing — `alembic` will fail on the slim image.                                            |
| 10 | High       | `docker-compose.yaml:149-156`                                    | `react-build` `working_dir` collides with bind-mount target; `oven/bun:1` is invalid.                        |
| 11 | High       | `docker-compose.yaml:150`                                        | `oven/bun:1` is not a published tag.                                                                         |
| 12 | Security   | `docker-compose.yaml:43,57-58`                                   | `api` + `rq-dashboard` bind `0.0.0.0` and publish on all interfaces; was loopback-only.                      |
| 13 | High       | `.env.docker.example:11,12,14`                                   | Template still uses legacy service name `db`.                                                                |
| 14 | Medium     | `docker-compose.yaml:158-163`                                    | `demetra_app_data` volume removed; worktrees / projects / venvs no longer persist across `down && up`.       |
| 15 | Info       | `demetra/services/persistence/database.py:97`                    | Sync URL uses `postgresql+psycopg://`; needs `psycopg-binary` to work on slim image.                         |
| 16 | Medium     | `docker-compose.yaml:30`                                         | `migrations` bind mount collides with the api bind-mount path; currently OK because api has no `:/srv/...` mount. |
| 17 | Low        | `pyproject.toml:3`                                               | Uncommitted version downgrade `1.18.0` → `1.16.1`.                                                           |
| 18 | Low        | `wiki/INDEX.md:10-14`                                            | Unresolved merge-conflict markers around the MNT-164 entry.                                                  |
| 19 | Low        | `Makefile:121`                                                   | `pull db redis react-build` — depends on Finding 11 being fixed first.                                       |
| 20 | Low        | `Makefile:99-100`                                                | `docker-run` target still hard-codes the legacy `manti` user.                                                |

**Count:** 7 Blocker · 5 High · 1 Security-critical (image-credential leak) · 1 Security (regression) · 3 Medium · 3 Low.

---

## Suggested fix order

1. **Finding 2** (`.dockerignore` + remove `COPY .keys/...`) — this stops leaking credentials on every subsequent rebuild.
2. **Findings 1, 3, 4** (Dockerfile final stage: re-add source `COPY`, fix venv path, fix `WORKDIR`) — three lines, unblocks all app services.
3. **Findings 5, 6, 8, 9** (compose: healthchecks, `DB_HOST: postgres` everywhere, `image: mantiby/demetra:latest`, `psycopg-binary`) — unblocks `migrate` and the long-running services.
4. **Finding 7** (`LOG_PATH` consistency) — unblocks import-time `dictConfig` on `worker` and `listener`.
5. **Findings 10, 11, 12, 13** (compose: `react-build` paths, `oven/bun:1.2`, loopback publishes, env template).
6. **Findings 14, 16, 17, 18, 19, 20** (volume persistence, version, wiki merge markers, Makefile `docker-run`).
7. **Finding 15** (informational; resolved by 9).

---

## Follow-ups

- Re-run `make docker-deploy` after the fix batch and re-validate against a live daemon (the original wiki did this end-to-end and surfaced every "compile-only" oversight).
- Audit whether `.keys/` should ever live in the build context at all — a `COPY .keys/...` in a Dockerfile is a strong code smell; prefer Docker secrets, runtime mounts, or init containers.
- Consider adding a `hadolint` step in CI to catch the obvious `WORKDIR` typos and the missing `.dockerignore` entries before they ship.

## Consistency note (2026-08-19)

Most findings were fixed in the subsequent anchor refactor (see [[2026-08-18-compose-anchors-refactor]]). Two findings were incorrect:

- **Finding 11** (`oven/bun:1` "not a valid tag"): `oven/bun:1` is a valid major-version tag on Docker Hub and is still used in the current compose.
- **Finding 12** (API/rq-dashboard "bind `0.0.0.0` and publish on all interfaces"): at the time of this review the port publishes were loopback-only (`127.0.0.1:8001:8001` and `127.0.0.1:9181:9181`), so the container-internal `--host 0.0.0.0` bind was not externally exposed. **Superseded (2026-08-23):** current `docker-compose.yaml` publishes on all interfaces (`8001:8001`, `9181:9181`), which reinstates this finding's concern — see [[2026-08-10-docker-compose-deploy]].

## References

- Related: [[2026-08-10-docker-compose-deploy]] (verified-good compose design this branch regressed)
- Related: [[2026-07-07-project-deploy-script]] (systemd deploy path; the compose is a parallel of this)
- Related: [[2026-08-18-compose-anchors-refactor]] (the DRY refactor that fixed most findings)
- Related: [[2026-08-19-worker-opencode-home-permissions]] (entrypoint ownership fix on the home volume)
- External: [MNT-164 — Docker compose (Linear)](https://linear.app/mnt/issue/MNT-164)
