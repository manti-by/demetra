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
related:
- 2026-08-20-review-gh-auth-mount-changes.md
- 2026-08-18-compose-anchors-refactor.md
- 2026-08-17-docker-setup-review.md
- 2026-08-10-docker-compose-deploy.md
---

# Worker opencode EACCES on home volume — entrypoint ownership fix

## TL;DR

Worker failed at plan step: `EACCES: permission denied, mkdir '/home/demetra/.local/share/opencode/repos'` — the `demetra_app_data` volume at `/home/demetra` (`docker-compose.yaml:15`) had root-owned dirs from before the `demetra` user existed, so `demetra` could not create `~/.local/share/opencode`. Fixed with a root entrypoint that repairs home-volume ownership once (marker `.home-ready`) while pruning secret bind mounts, then drops to `demetra` via `setpriv`.

## Symptom

`run_opencode_agent` (`demetra/services/agents/opencode.py:270`) → opencode CLI tries `~/.local/share/opencode` → EACCES. Worktree paths live under `HOME/.demetra/...` (`demetra/settings.py:41,160`).

## Why root-owned

- Image previously had `USER demetra` (uid 1000); image `/home/demetra` is demetra-owned, but named volume `demetra_app_data` is populated from image only when empty. Existing volume predates `demetra` user → top-level/subdirs root-owned.
- Volume holds worktrees, projects, venvs, opencode state. Worktrees later created demetra-owned, but `~/.local` stayed root-owned.

## Fix

Image `chown` cannot repair existing volume; fix runs at container start. Removed `USER demetra`, added `ENTRYPOINT ["docker-entrypoint.sh"]` (inherited by `migrate`, `api`, `worker`, `watcher`, `listener`, `rq-dashboard`).

`docker-entrypoint.sh`:
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
Prunes bind-mounted secrets (`.ssh`, `.gnupg`, `.gitconfig`, `.git-credentials`, `.local/share/opencode/auth.json`) so host ownership untouched. `HOME` exported explicitly since entrypoint runs as root. Verified via `sh -n` and `find -prune` dry-run.

> **Consistency note (2026-08-20):** prune list later extended to also skip `.config/gh/hosts.yml` — see [[2026-08-20-review-gh-auth-mount-changes]].

## Test Results

- `sh -n docker-entrypoint.sh` — OK; `find` dry-run — secret paths pruned, rest visited. Container build not run locally; `make docker-deploy` on amon-ra exercises entrypoint.

## Known follow-up

- If host `.keys/.ssh`/`.keys/.gnupg` not readable by uid 1000, SSH/gpg signing inside container may fail.

## Follow-ups

- Redeploy on amon-ra: `make docker-deploy`; verify `docker compose exec worker id demetra` → `uid=1000`.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-18-compose-anchors-refactor]], [[2026-08-17-docker-setup-review]], [[2026-08-10-docker-compose-deploy]]
