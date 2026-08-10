---
title: 'MNT-161: Process environment: 3 layers, encryption, UV venv, env file upload'
date: '2026-08-10'
type: implementation
status: reference
session_id: ses_01451c57dffevRjar67SFuonUS
services: [settings, database, subprocess, project, api, react, vcs, workflows]
branch: mnt-161-process-environment-3-layers-encryption-uv-venv-env-file-upload
tickets: [MNT-161]
tags: [environment, encryption, venv, subprocess, api]
related: [2026-08-10-process-environment-3-layers-encryption-uv-venv.md, 2026-06-08-project-environment.md]
---
# MNT-161: Process environment: 3 layers, encryption, UV venv, env file upload

> **Partial session note.** This page records the MNT-161 implementation session.
> The complete, canonical design is documented in
> [[2026-08-10-process-environment-3-layers-encryption-uv-venv]] — prefer that page.

## TL;DR

Implementation session for MNT-161: Process environment: 3 layers, encryption, UV venv, env file upload on branch `mnt-161-process-environment-3-layers-encryption-uv-venv-env-file-upload`. Two commits shipped the feature (`838d9b3`, `da1f965`): a three-layer environment merge (OS → user-shared → project → step), Fernet encryption with sensitive-key masking, per-project UV venv bootstrap, `/users/me/env` CRUD, and a FE "Shared environment" screen with client-side `.env` upload.

---

## Overview

Changed 46 file(s) (+2751 / −127 lines) affecting services: settings, database, subprocess, project, api, react, vcs, workflows. Primary files: `demetra/services/runtime/subprocess.py`, `demetra/services/runtime/project.py`, `demetra/services/persistence/database.py`, `react/src/utils/envFile.ts`.

## Changed files

- `demetra/settings.py` — `OS_ENV_ALLOWLIST`, `OS_ENV_PROJECT_OPTINS`, `DEMETRA_SECRET_KEY`
- `demetra/library/models.py`, `demetra/library/tables.py`, `migrations/versions/a6b7c8d9e0f1_add_environment_scope_and_user_id.py` — `scope`/`user_id` on `project_environment`, `EnvironmentEntry`/`EnvironmentUpsert`
- `demetra/services/persistence/database.py`, `demetra/services/persistence/encryption.py` — user-env CRUD + masking, Fernet encryption
- `demetra/services/runtime/subprocess.py` — `filter_os_env` + `build_subprocess_env` single merge point
- `demetra/services/runtime/project.py` — `setup_project_venv` UV venv bootstrap
- `demetra/services/vcs/git.py`, `github.py`, `merge.py`, `rebase.py` + `demetra/workflows/{setup,merge,rebase,cleanup}.py` — `project_id` threading through env builder call sites
- `demetra/api/users.py`, `demetra/api/projects.py` — `/users/me/env` CRUD, sensitive-key masking on project env
- `react/src/components/{SharedEnvSettings,EnvFileUploadButton,EnvSettings,Header}.tsx`, `react/src/utils/envFile.ts`, `react/src/services/api.ts` — shared-env screen + client-side `.env` upload
- `tests/` — settings, database, subprocess, venv bootstrap, API, envFile coverage

## Stat

```text
46 files changed, +2751 insertions(-) / -127 deletions
Backend: 793 tests pass (ruff, ty, pytest)
Frontend: 45 tests pass (tsc, vitest)
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

### 4. Alembic Migration
- Migration `a6b7c8d9e0f1_add_environment_scope_and_user_id` adds a `scope` column (`'project' | 'user'`, default `'project'`) and a nullable `user_id` FK to `users`.
- Partial unique indexes `uq_environment_project_key` (`project_id, key`) and `uq_environment_user_key` (`user_id, key`); check constraints `ck_environment_scope` / `ck_environment_owner` enforce exactly one owner matching `scope`.
- Additive; existing rows backfill to `scope = 'project'`.

### 5. Single Subprocess Environment Builder (merge order)
- `filter_os_env(project_id)` restricts `os.environ` to `OS_ENV_ALLOWLIST` plus per-project opt-in keys.
- `build_subprocess_env(extra, *, project_id, user_environment, project_environment, target_path)` merges the layers once, in order **OS → user-shared → project → step**, last writer winning; `PWD` is reserved and always overwritten by `target_path`.
- Both `run_command` and `run_command_to_file` route through it; workflow/agent overrides flow through the existing `env=` argument.

### 6. Per-Project UV Virtualenv
- `setup_project_venv(project)` in `demetra/services/runtime/project.py` runs `uv venv --seed <local_path>/.venv` on first use and reuses it afterward.
- Sets `VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT` (both allowlisted) on the cached project env and prepends the venv `bin` to `PATH`, so bare `python` resolves from the project venv.

### 7. `.env` File Upload (EnvFileUploadButton)
- Client-side parser `react/src/utils/envFile.ts` handles `export` prefixes, quotes, comments, and line continuations.
- Parsed entries are upserted through the existing env APIs (no dedicated endpoint); existing keys are updated, new keys inserted.
- Keys containing a whole sensitive word (`TOKEN`/`SECRET`/`KEY`/`PASSWORD`) default to `encrypted` so uploads are never stored in plaintext.

## Test Results

- Session status: `resolved`
- OpenCode session id: `ses_01451c57dffevRjar67SFuonUS`
- Backend: 793 tests pass (ruff, ty, pytest); frontend: 45 tests pass (tsc, vitest).

---

## Follow-ups

- Per-project encryption key derivation (single key from settings for now).
- Audit log for env changes.
- Docker-based isolation (deferred).

## References

- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]], [[2026-06-08-project-environment]]
- External: https://linear.app/mnt/issue/MNT-161/process-environment-3-layers-encryption-uv-venv-env-file-upload
