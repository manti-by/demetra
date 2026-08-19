---
title: Refactor API
date: 2026-06-01
type: implementation
status: resolved
session_id: "-"
services: [api]
branch: "-"
tickets: [MNT-81]
tags: [api, refactor, routers]
related: []
---

# Refactor API

## TL;DR

Split the too-long `demetra/api.py` into a `demetra/api/` package with routers grouped by route prefix (auth/github, projects, sessions, users, watcher, webhooks). The package keeps `@app.get`/`@app.post` decorators by importing `app` from the parent. Missing API tests were added. The refactor bundle landed GitHub OAuth, project CRUD, ticket creation with AI text processing, session tracking with status filtering, websocket log streaming, and user API key management.

---

## Overview

Monolithic `demetra/api.py` had grown to cover every subsystem. Grouping routes into a package by prefix makes each resource independently testable and editable. Note: this introduced `demetra/api/tickets.py`, later removed by MNT-88.

- `demetra/api/` package with per-prefix routers
- `@app.get`/`@app.post` decorators kept by importing `app` from the parent module
- Missing API tests added

## Step 1 — Split into a package

**File:** `demetra/api.py` → `demetra/api/`

Reorganized the single API module into a package with a router per route prefix: auth/github, projects, sessions, users, watcher, webhooks.

## Step 2 — Decorator pattern

Each router file keeps the `@app.get`/`@app.post` style by importing `app` from the parent package, so route registration and error handling stay consistent across files.

## Step 3 — Capabilities landed in the bundle

The refactor carried over the accumulated API surface: GitHub OAuth, project CRUD, ticket creation with AI text processing (`demetra/api/tickets.py`), session tracking with status filtering, websocket log streaming, and user API key management.

## Test Results

Missing API tests were added across the new router files.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-81
