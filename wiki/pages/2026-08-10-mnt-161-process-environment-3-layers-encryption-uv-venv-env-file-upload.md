---
title: 'MNT-161: Process environment: 3 layers, encryption, UV venv, env file upload'
date: '2026-08-10'
type: implementation
status: resolved
session_id: ses_01451c57dffevRjar67SFuonUS
services: []
branch: mnt-161-process-environment-3-layers-encryption-uv-venv-env-file-upload
tickets: [MNT-161]
tags: [wiki, feature]
related: []
---
# MNT-161: Process environment: 3 layers, encryption, UV venv, env file upload

## TL;DR

Implementation session for MNT-161: Process environment: 3 layers, encryption, UV venv, env file upload on branch `mnt-161-process-environment-3-layers-encryption-uv-venv-env-file-upload`.

---

## Overview

Changed 0 file(s) (0 lines) affecting services: none. Primary files: none.

## Changed files

- No changed files captured.

## Stat

```text
- no stat
```

## Build plan

## Implementation Plan
The implementation plan involves several steps to achieve the desired functionality for process environment handling. The key components of the plan are outlined below.

### 1. Add `OS_ENV_ALLOWLIST` and Per-Project Opt-In Support to Settings
- Add `OS_ENV_ALLOWLIST` as a frozenset of allowed environment variables.
- Add `OS_ENV_PROJECT_OPTINS` as a dictionary for per-project opt-in tokens.

### 2. Extend `Environment` Model and New Entry Dataclasses
- Update `Environment` dataclass to include `type` and `user_id`.
- Add `EnvironmentEntry` and `EnvironmentUpsert` dataclasses.

### 3. Extend the `project_environment` Table
- Rename `project_id` column to keep table name `project_environment`.
- Add `user_id` column and `scope` column for clarity.

### 4. Alembic Migra…

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_01451c57dffevRjar67SFuonUS`

---

## Follow-ups

- None

## References

- External: https://linear.app/mnt/issue/MNT-161/process-environment-3-layers-encryption-uv-venv-env-file-upload
