---
title: Bake opencode agents and skills into the Docker image
date: 2026-09-18
type: implementation
status: resolved
session_id: ses_f4b5d623fffe8VuQZEl0Uvm3ug
services: []
branch: "-"
tickets: []
tags: [docker, opencode, agents, skills, permissions]
related: [2026-08-17-docker-setup-review.md, 2026-08-19-worker-opencode-home-permissions.md, 2026-08-24-gh-config-dir-permission-entrypoint.md, 2026-09-14-opencode-agent-prompts-hardening.md]
---

# Bake opencode agents and skills into the Docker image

## TL;DR

`Dockerfile` now copies `.opencode/agents/` and `.opencode/skills/` into the image at `/home/demetra/.config/opencode/agents/` and `/home/demetra/.config/opencode/skills/` (plural names, matching opencode's global-config convention), owned by `demetra:demetra` with `755` dirs / `644` files. `.dockerignore` previously excluded the whole `.opencode` directory, which would have broken the `COPY` — it now re-includes just `agents/**` and `skills/**`. Committed as `ceac6b9` (plus a version bump in `pyproject.toml`).

---

## Overview

Demetra runs opencode agents (`plan-agent`, `build-agent`, `review-agent`, etc. via `demetra/services/agents/opencode.py`) with `--dir <target_path>`, so agents must resolve from the global config (`~/.config/opencode/`) rather than the target project's `.opencode/`. The image baked the opencode binary but never the agent/skill definitions, so containers relied on whatever happened to be mounted. The fix bakes the definitions in as `demetra`-owned, read-only-friendly files.

Path mapping (verified against [opencode agents docs](https://opencode.ai/docs/agents/) and [skills docs](https://opencode.ai/docs/skills/)):

- **File:** `.opencode/agents/*.md` → `/home/demetra/.config/opencode/agents/*.md` (global `~/.config/opencode/agents/`, per-project `.opencode/agents/`)
- **File:** `.opencode/skills/*/SKILL.md` → `/home/demetra/.config/opencode/skills/*/SKILL.md` (global `~/.config/opencode/skills/<name>/SKILL.md`)

## Step 1 — Dockerfile: COPY agents/skills with fixed ownership and modes

**File:** `Dockerfile:37-45`

Before: only `/home/demetra/.config/gh` and `/home/demetra/.local/share/opencode` were created; no agent/skill content was baked in.

After:

```
RUN mkdir -p /home/demetra/.config/gh /home/demetra/.config/opencode/agents /home/demetra/.config/opencode/skills /home/demetra/.local/share/opencode \
    && chown -R demetra:demetra /home/demetra

COPY --chown=demetra:demetra .opencode/agents/ /home/demetra/.config/opencode/agents/
COPY --chown=demetra:demetra .opencode/skills/ /home/demetra/.config/opencode/skills/
RUN chmod 755 /home/demetra/.config/opencode/agents /home/demetra/.config/opencode/skills \
    && find /home/demetra/.config/opencode/agents /home/demetra/.config/opencode/skills -type d -exec chmod 755 {} + \
    && find /home/demetra/.config/opencode/agents /home/demetra/.config/opencode/skills -type f -exec chmod 644 {} + \
    && chown -R demetra:demetra /home/demetra/.config/opencode
```

Why this shape:

- `mkdir` first so parent dirs exist with the right owner before `COPY`.
- `COPY --chown=demetra:demetra` so files never land root-owned (the failure mode behind [[2026-08-19-worker-opencode-home-permissions]] and [[2026-08-24-gh-config-dir-permission-entrypoint]]).
- Explicit `chmod` normalizes whatever modes the build context carries: dirs `755`, files `644`, matching the source tree (`ls -l` showed `-rw-r--r--` / `drwxr-xr-x`).
- Trailing `chown -R` covers parent dirs Docker creates as root during `COPY`.

## Step 2 — .dockerignore: re-include agents/skills

**File:** `.dockerignore:15-19`

`.dockerignore` excluded the entire `.opencode` directory, which would have made the new `COPY` instructions fail with "not found". Added narrow exceptions so only the needed subtrees enter the build context:

```
.opencode
!.opencode/agents/
!.opencode/agents/**
!.opencode/skills/
!.opencode/skills/**
```

`.opencode/node_modules`, `package.json`, and other `.opencode/*` entries stay excluded.

## Test Results

- Verified source layout: 8 files in `.opencode/agents/` (`build-agent.md`, `merge-agent.md`, `plan-agent.md`, `rebase-agent.md`, `research-agent.md`, `resolve-agent.md`, `review-agent.md`, `validate-agent.md`) and 8 skill dirs under `.opencode/skills/`, each with `SKILL.md`.
- Verified source modes are already `644` files / `755` dirs, so the in-image `chmod` is a normalization, not a change of intent.
- No full `docker build` run in this session (heavy: `uv sync` + opencode install); change was committed as `ceac6b9` by the pipeline and the working tree is clean.
- No `pytest`/`ruff` impact: only `Dockerfile` + `.dockerignore` (+ version bump) touched.

---

## Follow-ups

- Stale-volume caveat: `docker-compose.yaml` mounts `demetra_app_data:/home/demetra/`, so containers created from an older volume will not see the newly baked agents/skills until the volume is recreated. Consider an entrypoint refresh (rsync from a pristine baked copy) if stale agents become a problem.
- Consider baking `opencode.json` command definitions next, if containers need the `/skill:*` command wiring without a project mount.

> **Consistency fix (2026-09-28, Consistency Agent):** quoted bare `branch: -` (invalid YAML) and normalized `related:` entries to `.md` filenames. The "8 skill dirs" claim above was true at commit `ceac6b9` (verified: `fix-review-findings`, `release-name`, `release-notes`, `wiki-agents-file`, `wiki-archive`, `wiki-consistency`, `wiki-dedup`, `wiki-sync`); 7 of them were deleted in `94fefa7` (2026-09-23) — only `.opencode/skills/wiki-sync/` remains on HEAD.

## References

- Related: [[2026-08-17-docker-setup-review]]
- Related: [[2026-08-19-worker-opencode-home-permissions]]
- Related: [[2026-08-24-gh-config-dir-permission-entrypoint]]
- Related: [[2026-09-14-opencode-agent-prompts-hardening]]
- External: https://opencode.ai/docs/agents/
- External: https://opencode.ai/docs/skills/
