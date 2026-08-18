---
title: Add SQLAlchemy Core support
date: 2026-03-13
type: implementation
status: resolved
session_id: -
services: [database, tests]
branch: -
tickets: [MNT-62]
tags: [sqlalchemy, database, alembic, testing]
related: []
---

# Add SQLAlchemy Core support

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-03-fix-squash-migrations]]. See wiki/archive/ for the
> original.

## TL;DR

Replaced raw SQL with SQLAlchemy Core (Core only, no declarative base): `demetra/services/database.py` now uses `Table`/`Column` objects. Tests run against a Postgres database with the same schema and a `test_` prefix, created once per test session with transaction rollback, and Alembic was introduced with an initial migration from the current DB state (migrations in `alembic/` at the project root, later consolidated into `migrations/`). SQLAlchemy 2.0.48.

---

## Overview

Moves the data layer off handwritten SQL strings onto a maintained query builder, and gives the schema a migration story. Tests stop mocking the DB and exercise real queries against Postgres.

- `demetra/services/database.py` reworked to use `Table`/`Column` objects
- Core-only, no declarative base
- pytest uses a Postgres DB with the same schema + `test_` prefix, created once per session with transaction rollback
- Alembic with an initial migration from current DB state
- DB mocks removed in favor of factories + real queries
- SQLAlchemy 2.0.48

## Step 1 — SQLAlchemy Core tables

**File:** `demetra/services/database.py`

Reworked the database module to define tables as SQLAlchemy Core `Table`/`Column` objects and express all queries with the Core API instead of raw SQL.

## Step 2 — Alembic migrations

Added Alembic support with an initial migration generated from the current DB state. Migrations live in `alembic/` at the project root (later consolidated into `migrations/`).

## Step 3 — Real-query test infra

Tests now run against a Postgres database with the same schema under a `test_` prefix. The DB is created once per test session and tests run in transactions that roll back. DB mocks were dropped in favor of factories plus real queries.

## Test Results

Tests were updated to run against Postgres and exercise real SQLAlchemy queries.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-62
