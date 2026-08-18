---
title: Postgres Support
date: 2026-03-05
type: implementation
status: resolved
session_id: -
services: [database, settings]
branch: -
tickets: [MNT-51]
tags: [database, postgres, sqlite, migration]
related: []
---

# Postgres Support

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-03-fix-squash-migrations]]. See wiki/archive/ for the
> original.

## TL;DR

Replaced SQLite with PostgreSQL as the backing store: added an async PostgreSQL client (`psycopg-binary`), rewrote all SQLite queries for Postgres, and moved DB connection parameters to env-driven settings (`DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, all defaulting to `demetra`). README and agent docs were updated, pre-commit hook versions bumped, and the prompt guidance clarified that questions must end with a trailing question mark.

---

## Overview

Database migration off SQLite so the app can run a real multi-user database. All query paths were updated in one pass, and the DB connection became configurable via environment variables.

- Async PostgreSQL client + `psycopg-binary`
- All SQLite queries replaced with Postgres equivalents
- Env-driven connection parameters in settings
- Docs, pre-commit hooks, and prompt guidance updated

## Step 1 — PostgreSQL client

Switched the database layer to an async PostgreSQL client with `psycopg-binary` as the driver.

## Step 2 — Rewrite queries

Replaced every SQLite query in the data layer with the Postgres equivalent (syntax, placeholders, and type handling).

## Step 3 — Settings

**File:** `demetra/settings.py`

Connection parameters are now read from environment variables with defaults:

- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- Default value: `demetra`

This removes hardcoded connection strings from the codebase.

## Step 4 — Docs and tooling

- README and agent docs updated for the new DB setup
- Pre-commit hook versions bumped
- Prompt guidance clarified: questions must end with a trailing question mark

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-51
