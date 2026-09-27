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
related:
- 2026-08-19-worker-opencode-home-permissions.md
- 2026-08-18-compose-anchors-refactor.md
- 2026-08-17-docker-setup-review.md
---

# Code review — gh CLI auth mount and entrypoint prune for compose

## TL;DR

Reviewed working-tree changes adding `gh` auth to Docker: bind mount `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` and matching `find -prune` entry. Found one critical bug — missing `-o` between the two `-path` clauses caused implicit AND (always false), silently disabling the prune for both `hosts.yml` and `auth.json`. Compose mount itself was consistent with existing `.keys/` pattern. Fixed before merge (PR #83).

## Findings

### 1. Missing `-o` in `find` prune — Critical

`configs/docker-entrypoint.sh:9-11` — before fix:
```sh
\( -path /home/demetra/.config/gh/hosts.yml \
   -path /home/demetra/.local/share/opencode/auth.json \
   -o -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
```
Adjacent `find` expressions without operator are implicit AND; one file cannot match two full paths → always false. Both `hosts.yml` and `auth.json` not pruned (regression of [[2026-08-19-worker-opencode-home-permissions]]); recursive `chown` would walk into bind mounts and try to change host file ownership.

Fix — add `-o`:
```sh
\( -path /home/demetra/.config/gh/hosts.yml \
   -o -path /home/demetra/.local/share/opencode/auth.json \
   -o -name .ssh -o -name .gnupg -o -name .gitconfig -o -name .git-credentials \) -prune \
```

### 2. Compose gh mount — No issue

`docker-compose.yaml:21` — `.keys/gh/hosts.yml:/home/demetra/.config/gh/hosts.yml` matches existing `.keys/` secret mount pattern (`.keys/opencode/auth.json`, `.keys/.ssh`, etc.). Docker auto-creates parent `.config/gh/`. Host dir provisioned on deploy host, consistent.

## Summary

1 Critical (missing `-o`, prune disabled for both bind mounts) · 1 None. Count: 1 Critical · 1 None.

## Consistency note (2026-08-20)

Fixed in `configs/docker-entrypoint.sh` before merge to `master` (PR #83). Current tree uses `-o` between both `-path` clauses.

## Follow-ups

- Provision `.keys/gh/hosts.yml` on deployment host.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-19-worker-opencode-home-permissions]], [[2026-08-18-compose-anchors-refactor]], [[2026-08-17-docker-setup-review]]
