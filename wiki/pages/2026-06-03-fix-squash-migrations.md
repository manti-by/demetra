---
title: Fix and squash migrations
date: 2026-06-03
type: implementation
status: resolved
session_id: -
services: [database, alembic]
branch: -
tickets: [MNT-99]
tags: [migrations, alembic, squash]
related: []
---

# Fix and squash migrations

## TL;DR

Dropped the accumulated migration chain and replaced it with a single consolidated migration, updating the existing local database so `alembic upgrade` no longer errors. DB connection initialization was updated to modern config patterns, and `projects.repository_url` became a required column.

---

## Overview

The migration history had drifted from the schema and broke `alembic upgrade`. Squashing it into one migration resets the baseline; the acceptance criterion is that `alembic upgrade` runs without errors.

- Existing migrations dropped
- Single new consolidated migration created
- Existing database migrated to the new baseline
- `alembic upgrade` no longer errors
- DB connection init updated to modern config patterns
- `projects.repository_url` became required

## Step 1 — Squash the migration chain

Dropped the existing migrations and created one new consolidated migration that captures the current schema, so the history no longer has dead/conflicting steps.

## Step 2 — Migrate the local database

Updated the existing database to the new consolidated baseline.

## Step 3 — Connection config

Updated DB connection initialization to modern config patterns (env-driven connection settings).

## Step 4 — Required column

`projects.repository_url` became a required column as part of the consolidated schema.

## Test Results

Acceptance: `alembic upgrade` runs without errors against the migrated database.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-99
