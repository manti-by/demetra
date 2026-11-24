---
title: Project model and space
generated: {by: demetra, at: '2026-03-31T00:00:00Z'}
description: Records MNT-75, which moved projects from a settings dict to a per-user `Project` model with a migration and user-scoped CRUD APIs that provision a checked-out repo and a Postgres role/database (path corrected to a project-id suffix), plus a React list; the page was later archived and merged into the project-environment page.
type: implementation
status: deprecated
session_id: '-'
services: [database, api, react]
branch: '-'
tickets: [MNT-75]
tags: [projects, database, provisioning, react]
related: [2026-04-02-link-user-tasks-sessions.md, 2026-06-08-project-environment.md]
---

# Project model and space

> **Archived on 2026-10-26.** Useful info merged into
> [2026-06-08-project-environment](/archive/2026-06-08-project-environment.md). See wiki/archive/ for the original.

## TL;DR

Replaced the dict-mapped projects in settings with a `Project` database model linked to the logged-in user (`user_id`, `linear_project_id`, `name`, `repository_url`), including a migration that moved existing projects out of `LINEAR["projects"]` and CRUD APIs scoped to the authenticated user. On add, the API provisions a workspace: `~/.demetra/projects/<owner>/<repo>/`, `git clone`, and a Postgres role + database named after the project (sanitized via slugify). A React project component lists projects in the settings section.

> **Correction (2026-10-26, Consistency Agent):** the checkout path also carries a project-id suffix — `WORKTREE_PATH / repository_owner / slugify(f"{repository_name}-{project['id'][:8]}")` (`demetra/services/runtime/project.py:65,123`, `WORKTREE_PATH` at `demetra/settings.py:36`), i.e. `~/.demetra/projects/<owner>/<repo>_<8-char-id>/`, not `<owner>/<repo>/`.

---

## Overview

Projects previously lived as a static dict in settings. Moving them to the DB makes them per-user and creates a real project space on disk and in Postgres.

- `Project` model (`user_id`, `linear_project_id`, `name`, `repository_url`)
- Migration moving existing projects from `LINEAR["projects"]` to the DB
- CRUD APIs always scoped to the authenticated user
- Provisioning on add: clone + Postgres role/database
- React project component + list in the settings section

## Step 1 — Project model and migration

Added the `Project` model linked to the user, and a migration that moves projects previously configured under `LINEAR["projects"]` in settings into the database.

## Step 2 — CRUD APIs

Added project CRUD endpoints, all scoped to the authenticated user. Default auth, exception handling, and logging are applied to the new APIs. Task/session user-scoping built on top of this model is recorded in [2026-04-02-link-user-tasks-sessions](/archive/2026-04-02-link-user-tasks-sessions.md).

## Step 3 — Provisioning on add

**File:** `demetra/services/project.py`

Adding a project creates its workspace:

- `~/.demetra/projects/<owner>/<repo>_<8-char-project-id>/` directory (project-id suffix per `demetra/services/runtime/project.py:65,123`)
- `git clone` of the repository
- A Postgres role + database named after the project, sanitized via slugify

## Step 4 — React component

Added a project component and list in the React settings section backed by the CRUD API.

## Test Results

Tests were added for the project model, CRUD API, and provisioning.

---

## Follow-ups

- None.

> **Consistency fix (2026-09-18, Consistency Agent):** Quoted bare `session_id: -` / `branch: -` for valid YAML and mirrored body links into `related:` frontmatter.

## References

- Related: [2026-04-02-link-user-tasks-sessions](/archive/2026-04-02-link-user-tasks-sessions.md), [2026-06-08-project-environment](/archive/2026-06-08-project-environment.md)
- External: https://linear.app/mnt/issue/MNT-75
