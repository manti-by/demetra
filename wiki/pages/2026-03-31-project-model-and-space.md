---
title: Project model and space
date: 2026-03-31
type: implementation
status: resolved
session_id: -
services: [database, api, react]
branch: -
tickets: [MNT-75]
tags: [projects, database, provisioning, react]
related: []
---

# Project model and space

## TL;DR

Replaced the dict-mapped projects in settings with a `Project` database model linked to the logged-in user (`user_id`, `linear_project_id`, `name`, `repository_url`), including a migration that moved existing projects out of `LINEAR["projects"]` and CRUD APIs scoped to the authenticated user. On add, the API provisions a workspace: `~/.demetra/projects/<owner>/<repo>/`, `git clone`, and a Postgres role + database named after the project (sanitized via slugify). A React project component lists projects in the settings section.

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

Added project CRUD endpoints, all scoped to the authenticated user. Default auth, exception handling, and logging are applied to the new APIs.

## Step 3 — Provisioning on add

**File:** `demetra/services/project.py`

Adding a project creates its workspace:

- `~/.demetra/projects/<owner>/<repo>/` directory
- `git clone` of the repository
- A Postgres role + database named after the project, sanitized via slugify

## Step 4 — React component

Added a project component and list in the React settings section backed by the CRUD API.

## Test Results

Tests were added for the project model, CRUD API, and provisioning.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-75
