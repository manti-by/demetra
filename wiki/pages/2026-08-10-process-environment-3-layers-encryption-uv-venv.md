---
title: Process environment — 3 layers, encryption, UV venv, env file upload
date: 2026-08-10
type: implementation
status: resolved
session_id: '-'
services:
- database
- subprocess
- workflows
- api
- react
branch: mnt-161-process-environment-3-layers-encryption-uv-venv-env-file-upload
tickets:
- MNT-161
- MNT-56
- MNT-110
- MNT-75
tags:
- environment
- encryption
- venv
- subprocess
- api
- user-settings
- keys
- per-project
- projects
- provisioning
- postgres
related:
- 2026-03-09-encrypted-user-settings.md
- 2026-06-08-project-environment.md
- 2026-03-31-project-model-and-space.md
---
# Process environment — 3 layers, encryption, UV venv, env file upload

## TL;DR

Extended per-project env into three layers — OS (allowlisted) → user-shared → project → step (last writer wins). Sensitive values encrypted via Fernet (`SECRET_KEY`+`ENCRYPTION_SALT`) and masked in API/UI, including plaintext keys containing a whole sensitive word (`TOKEN`/`SECRET`/… delimiter-anchored). Each RQ worker bootstraps a per-project UV venv on first use. FE gained a Shared environment screen and client-side `.env` upload via existing editors.

---

## Overview

Previously ([[2026-06-08-project-environment]]) every subprocess got `os.environ` + one project dict. Now three layers merged in one place (`build_subprocess_env`), with step overrides on top.

## Step 1 — Three layers in settings

**Files:** `demetra/library/constants.py`, `demetra/settings.py`

- `OS_ENV_ALLOWLIST` — frozenset of safe host keys (`PATH`, `HOME`, `LANG`, `TZ`, `VIRTUAL_ENV`, `SSH_AUTH_SOCK`/`GIT_SSH_COMMAND`, proxy vars, …); everything else dropped. SSH/proxy allowlisted unconditionally so git/gh work from daemon/wiki call sites.
- `OS_ENV_PROJECT_OPTINS` — `OS_ENV_PROJECT_OPTINS` env (`project-a=GITHUB_TOKEN,…;project-b=AWS_PROFILE`) → per-project extra keys.
- `SECRET_KEY` — Fernet key via `persistence/encryption.py`; not versioned, no fallback — changing it requires re-encrypting stored values.

## Step 2 — Data model

**Files:** `demetra/library/tables.py`, `demetra/library/models.py`, migration `a6b7c8d9e0f1`

- `project_environment` adds `scope` (`project`|`user`, default `project`) + nullable `user_id` FK.
- Partial unique indexes `uq_environment_project_key` / `uq_environment_user_key`; checks `ck_environment_scope`/`ck_environment_owner`.
- Existing rows backfilled to `project`. `Environment` extended with `project_id`/`user_id`/`scope`; new `EnvironmentEntry`, `EnvironmentUpsert`, `is_sensitive_key()`.

## Step 3 — DB helpers

**File:** `demetra/services/persistence/database.py` — new `scope='user'` functions mirroring project ones: `get_user_environments_decrypted`, `list_user_environments` (masked), `upsert_user_environment` (encrypts), `delete_user_environment`. Project functions now filter `scope='project'`.

## Step 4 — Single env builder

**File:** `demetra/services/runtime/subprocess.py`

`filter_os_env(project_id)` → allowlist + per-project opt-ins. `build_subprocess_env(extra, *, project_id, user_environment, project_environment, target_path)` merges OS→user→project→step; `PWD` always set from `target_path` (overwrites any layer). All `run_command`/`run_command_to_file` call it. Workflow call sites pre-merge user env under project env; `project_id` threaded through git/gh for consistent opt-ins.

## Step 5 — Per-project UV venv

**File:** `demetra/services/runtime/project.py` — `setup_project_venv(project)` runs `uv venv --seed <local>/.venv` first time, reuses after. Sets `VIRTUAL_ENV`/`UV_PROJECT_ENVIRONMENT` (+ prepends venv `bin` to `PATH`) so bare `python` resolves to project venv.

## Step 6 — API

- `GET/PUT/DELETE /api/v1/users/me/env[/key]` (`demetra/api/users.py`) — current user only (`get_current_user_dep`), no admin override.
- Project endpoints (`demetra/api/projects.py`) now also mask `is_sensitive_key` plaintext (e.g. `STRIPE_API_KEY` → `********`); same for `list_user_environments`.

## Step 7 — React

- Burger → **Shared environment** (`Header.tsx` → `SharedEnvSettings`/`App.tsx`) reuses project-editor UX against `/users/me/env`.
- Both editors have **Upload .env** (`EnvFileUploadButton.tsx` + `utils/envFile.ts` handling `export`, quotes, comments, continuations). Parsed entries upserted via existing APIs; sensitive-key entries default to `encrypted`. No dedicated upload endpoint.

## Test Results

793 backend (`ruff`/`ty`/`pytest`), 45 frontend (`tsc`+`vitest`) pass. Coverage: settings parsing, user-env CRUD+encryption+isolation+masking, merge order, allowlist, API endpoints, `is_sensitive_key` false-positives, venv idempotency, `.env` parser.

---

## Source — [[2026-03-09-encrypted-user-settings]]

MNT-56 (2026-03-09): `User.keys` encrypted via `SECRET_KEY`/`ENCRYPTION_SALT`; origin of env encryption and user-shared concept.

## Source — [[2026-06-08-project-environment]]

MNT-110: `project_id/key/value` → `Project.environment` passed to subprocesses.

## Follow-ups

- Per-project encryption key derivation; audit log; Docker-based isolation (deferred).

## References

- Related: [[2026-03-09-encrypted-user-settings]], [[2026-06-08-project-environment]], [[2026-03-31-project-model-and-space]]
- External: [MNT-161](https://linear.app/mnt/issue/MNT-161)
