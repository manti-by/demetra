---
title: Code review — gh CLI auth mount and entrypoint prune for compose
date: 2026-08-20
type: code-review
status: resolved
session_id: ses_fe1f1413cffe0nPjQ3DdiuD5IG
services: [deploy, configs]
branch: "-"
tickets: []
tags: [docker, compose, review, entrypoint, security]
related: [2026-08-19-worker-opencode-home-permissions.md, 2026-08-18-compose-anchors-refactor.md, 2026-08-17-docker-setup-review.md]
---

# Code review — gh CLI auth mount and entrypoint prune for compose

## TL;DR

Reviewed the working-tree changes that pass GitHub CLI (`gh`) authentication into the Docker deployment: a new bind mount `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` in `docker-compose.yaml` and a matching prune entry in `configs/docker-entrypoint.sh`. Found one **critical bug**: the new `-path` prune clause was added without the `-o` operator, so `find` ANDs it with the existing `auth.json` `-path` (always false) — silently disabling the prune for both `hosts.yml` and the previously-protected `auth.json`. The compose mount itself is consistent with the existing `.keys/` mount pattern. The missing `-o` was fixed before merge (see consistency note below).

---

## Findings

### 1. Missing `-o` operator in the `find` prune expression

**File:** `configs/docker-entrypoint.sh:9-11`

**Severity:** Critical.

**Problem:** The new `-path` for the gh config was inserted directly before the existing `auth.json` `-path` with no operator between them:

```sh
\( -path /home/demetra/.config/gh/hosts.yml \
   -path /home/demetra/.local/share/opencode/auth.json \
   -o -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
```

In `find`, adjacent expressions without an explicit operator are joined by **implicit AND**. A single file can never match two different full paths, so `-path .../hosts.yml AND -path .../auth.json` is always false. The practical result:

- `hosts.yml` is **not** pruned — the recursive `chown -h demetra:demetra` walks into the bind mount and attempts to change ownership of the host file.
- `auth.json` is **not** pruned either — a **regression** of the previously-working protection added in [[2026-08-19-worker-opencode-home-permissions]].

**Fix:** Add `-o` between the two `-path` clauses so each is an alternative:

```sh
\( -path /home/demetra/.config/gh/hosts.yml \
   -o -path /home/demetra/.local/share/opencode/auth.json \
   -o -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
```

### 2. Compose gh mount — consistent, no change needed

**File:** `docker-compose.yaml:21`

**Severity:** None.

**Problem:** None. `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` follows the exact pattern of the other secret mounts (`.keys/opencode/auth.json`, `.keys/.ssh`, `.keys/.gnupg`, ...). Docker auto-creates the parent directory `.config/gh/` inside the container. The `.keys/gh/` host dir does not exist locally, but neither does `.keys/opencode/` — both are provisioned on the deployment host, consistent with the existing setup.

---

## Summary

- **#1** — **Critical** — `configs/docker-entrypoint.sh:9-11` — missing `-o` between the `hosts.yml` and `auth.json` `-path` clauses; prune silently disabled for both bind mounts.
- **#2** — **None** — `docker-compose.yaml:21` — gh hosts.yml mount consistent with existing `.keys/` pattern; no change needed.

**Count:** 1 Critical · 1 None.

---

## Consistency note (2026-08-20)

The missing `-o` between the `hosts.yml` and `auth.json` `-path` clauses was fixed in `configs/docker-entrypoint.sh` before merge to `master` (PR #83). Current tree:

```sh
\( -path /home/demetra/.config/gh/hosts.yml \
   -o -path /home/demetra/.local/share/opencode/auth.json \
   -o -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
```

## Follow-ups

- Provision `.keys/gh/hosts.yml` on the deployment host (same step as `.keys/opencode/auth.json`).

## References

- Related: [[2026-08-19-worker-opencode-home-permissions]] (original entrypoint prune list this change extends)
- Related: [[2026-08-18-compose-anchors-refactor]] (volume anchor block the mount was added to)
- Related: [[2026-08-17-docker-setup-review]] (prior compose review; security posture for `.keys/`)