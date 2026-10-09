---
title: Project environment
date: 2026-06-08
type: implementation
status: resolved
session_id: '-'
services: [database, subprocess, workflows]
branch: '-'
tickets: [MNT-110, MNT-75]
tags: [environment, subprocess, per-project, projects, provisioning, postgres]
related: [2026-03-31-project-model-and-space.md, 2026-08-10-process-environment-3-layers-encryption-uv-venv.md]
---

# Project environment
> **Consolidated 2026-09-14.** Still live in `wiki/pages/` — this is the session
> record, not an archived page. Its reusable content was merged into
> [[2026-08-10-process-environment-3-layers-encryption-uv-venv]], the page to read for the current state of that subsystem.
> The `wiki/archive/` copy this banner used to point at was removed in
> `70144cb` (2026-09-18), so there is no separate original.

## TL;DR

Added per-project environment variables that are applied to every subprocess the supervisor spawns. A new `Environment` model (`project_id` FK, `key`, `value`) holds one-to-many records per project; the `Project` dataclass in `Context` builds a cached `environment` dict from them and it is passed wherever a subprocess runs. Migration + tests. MNT-109 was the earlier partial attempt (PR #49, closed).

---

## Overview

Different projects need different environment variables (tokens, paths, flags). Previously every subprocess inherited only the supervisor process environment. This change makes project settings reach git, workflow steps, and agent commands.

## Step 1 — Persist environment records

**File:** `Environment` model

New model with `project_id` FK, `key`, and `value` — one project maps to many environment records. Alembic migration included.

## Step 2 — Expose a cached environment dict

**File:** `Project` dataclass in `Context`

`Project` gains a cached `environment` dict built from the linked `Environment` records. The records are fetched right after `Project` on session setup, so they are available before the workflow starts.

## Step 3 — Pass environment to every subprocess

**File:** `subprocess` runner / workflow steps

The environment is passed everywhere a subprocess is spawned:

- git,
- CI / workflow steps,
- code-analysis, lint, and test,
- agent commands.

Review/build/resolve workflows and agent executions honor the overrides.

## Test Results

Tests cover the `Environment` model, the cached dict construction, and that subprocess calls receive the merged per-project environment.

---

## Source — [[2026-03-31-project-model-and-space]]

Originally added in [[2026-03-31-project-model-and-space]] on 2026-03-31 (MNT-75): the
`Project` model (user_id, linear_project_id, name, repository_url) and its table were
introduced here, with user-scoped CRUD, replacing the earlier `LINEAR["projects"]`
config-driven approach. A project's workspace is provisioned at
`~/.demetra/projects/<owner>/<repo>/` with a git clone and a dedicated Postgres
role/database (names slugified). This is the model this page's `Project` dataclass and
`Environment` records hang off, and the origin of the per-project workspace the
MNT-161 UV venv lives in.

## Follow-ups

None.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-03-31-project-model-and-space]], [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- External: [MNT-110 — Project environment (Linear)](https://linear.app/mnt/issue/MNT-110)
