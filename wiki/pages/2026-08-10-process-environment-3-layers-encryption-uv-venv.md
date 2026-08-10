---
title: Process environment — 3 layers, encryption, UV venv, env file upload
date: 2026-08-10
type: implementation
status: resolved
session_id: -
services: [database, subprocess, workflows, api, react]
branch: mnt-161-process-environment-3-layers-encryption-uv-venv-env-file-upload
tickets: [MNT-161]
tags: [environment, encryption, venv, subprocess, api]
related: [2026-06-08-project-environment.md]
---

# Process environment — 3 layers, encryption, UV venv, env file upload

## TL;DR

Extended per-project env ([MNT-110](https://linear.app/mnt/issue/MNT-110)) into a three-layer model — OS (allowlisted), user-shared (per-user), and project (per-project) — merged as **OS → user-shared → project → step** with the last writer winning. Sensitive values are encrypted at rest via Fernet (`DEMETRA_SECRET_KEY` + `ENCRYPTION_SALT`) and masked in the API/UI, including plaintext values whose key contains a whole sensitive word (`TOKEN`/`SECRET`/`KEY`/`PASSWORD`, delimiter-anchored so `KEYBOARD_LAYOUT` stays visible). Each RQ worker bootstraps a per-project UV venv on first use and reuses it. The FE gained a "Shared environment" screen and client-side `.env` file upload that populates the existing editors; no dedicated upload endpoint.

---

## Overview

Previously ([MNT-110](https://linear.app/mnt/issue/MNT-110)) every subprocess received `os.environ` merged with a single per-project env dict. This change formalizes three layers and merges them in exactly one place (`build_subprocess_env`), so workflow/agent-step overrides sit on top of all three.

## Step 1 — Three env layers in settings

**File:** `demetra/settings.py`

- `OS_ENV_ALLOWLIST` — a frozenset of safe host-OS keys (`PATH`, `HOME`, `USER`, `LANG`, `TZ`, `VIRTUAL_ENV`, `UV_PROJECT_ENVIRONMENT`, SSH agent vars `SSH_AUTH_SOCK`/`SSH_AGENT_PID`/`GIT_SSH_COMMAND`, proxy vars `http_proxy`/`https_proxy`/`HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`/`all_proxy`, …) that are forwarded verbatim. Anything else from the host OS is dropped. SSH-agent and proxy keys are allowlisted unconditionally so credential-bearing git/gh commands (clone/fetch/push/`gh api`) keep working even from daemon/wiki call sites that have no project context.
- `OS_ENV_PROJECT_OPTINS` — parsed from the `OS_ENV_PROJECT_OPTINS` env var (`project-a=GITHUB_TOKEN,GITHUB_ACTIONS;project-b=AWS_PROFILE`) into a per-project registry of extra keys to forward.
- `DEMETRA_SECRET_KEY` — new setting that falls back to `SECRET_KEY`; the encryption service now derives the Fernet key from it (rotate-friendly).

## Step 2 — Data model: scope + user_id

**File:** `demetra/library/tables.py`, `demetra/library/models.py`, migration `a6b7c8d9e0f1`

- `project_environment` gains a `scope` column (`'project' | 'user'`, default `'project'`) and a nullable `user_id` FK to `users`.
- Partial unique indexes: `uq_environment_project_key` on `(project_id, key)` where `project_id IS NOT NULL`, and `uq_environment_user_key` on `(user_id, key)` where `user_id IS NOT NULL`.
- Check constraints `ck_environment_scope` and `ck_environment_owner` (exactly one of `project_id`/`user_id` set, matching `scope`).
- Existing rows are backfilled to `scope = 'project'` by the column server default; the migration is additive.
- `Environment` dataclass extended with `project_id`/`user_id`/`scope`; new `EnvironmentEntry`, `EnvironmentUpsert`, and `is_sensitive_key()`.

## Step 3 — DB helpers for user-shared env

**File:** `demetra/services/persistence/database.py`

New functions mirroring the project-env ones, all scoped to `scope = 'user'`:

- `get_user_environments_decrypted(user_id)` — decrypted dict for subprocess merging.
- `list_user_environments(user_id)` — masked list for the API.
- `upsert_user_environment(user_id, key, value, env_type)` — encrypts on write, masks on return.
- `delete_user_environment(user_id, key)`.

Project-env functions were updated to filter `scope = 'project'` explicitly, and `upsert_project_environment` writes `scope = 'project'` using the partial-index `ON CONFLICT` clause.

## Step 4 — Single subprocess env builder

**File:** `demetra/services/runtime/subprocess.py`

`filter_os_env(project_id)` returns `os.environ` restricted to `OS_ENV_ALLOWLIST` plus the project's opt-in keys. `build_subprocess_env(extra, *, project_id, user_environment, project_environment, target_path)` merges the layers in order and sets `PWD`. Both `run_command` and `run_command_to_file` call it — this is the one place the subprocess environment is assembled. The workflow call sites (setup/merge/rebase/cleanup) pre-merge the user-shared env under the project env into `project.environment`, so project overrides user-shared on key conflict; per-step overrides flow through the existing `env=` argument, and `project_id` is threaded through the git/gh services so per-project OS opt-ins apply consistently.

## Step 5 — Per-project UV venv

**File:** `demetra/services/runtime/project.py`

`setup_project_venv(project)` runs `uv venv --seed <local_path>/.venv` on first use and reuses the existing directory afterwards. It sets `VIRTUAL_ENV` and `UV_PROJECT_ENVIRONMENT` on the cached project environment (both are in the OS allowlist), so every subprocess runs inside the project venv. `setup_workflow`, merge, and rebase workflows all call it. No Docker.

## Step 6 — API

- `GET/PUT/DELETE /api/v1/users/me/env[/key]` (`demetra/api/users.py`) — user-shared env CRUD for the current user only; the user id always comes from `get_current_user_dep`, so there is no admin override of another user's env.
- Project env endpoints (`demetra/api/projects.py`) keep working and now also mask plaintext values whose key contains a whole sensitive word (`is_sensitive_key`), e.g. `STRIPE_API_KEY` is returned as `********` even when stored as `text`. The user-shared list (`list_user_environments`) applies the same masking.

## Step 7 — React

- New burger-menu entry **Shared environment** (`Header.tsx`) opens `SharedEnvSettings` (`App.tsx`), which reuses the project env editor UX (masked display, add/remove, encrypted checkbox) against `/users/me/env`.
- Both the project and shared env editors render an **Upload .env** button (`EnvFileUploadButton.tsx`) backed by a client-side parser (`utils/envFile.ts`, handles `export` prefix, quotes, comments, line continuations). Parsed entries are upserted as new rows via the existing env APIs — no dedicated upload endpoint. Entries whose key contains a whole sensitive word default to `encrypted` so uploaded secrets are never stored in plaintext.
- Help text on both screens: "User-shared env is applied to all your projects. Project env overrides user-shared on key conflict."

## Test Results

793 backend tests pass (`ruff`, `ty`, `pytest`), 45 frontend tests pass (`tsc` via `bun run build`, `vitest`). New coverage: settings parsing (`OS_ENV_ALLOWLIST`/`OS_ENV_PROJECT_OPTINS`/`DEMETRA_SECRET_KEY`), user-env DB CRUD + encryption + isolation + sensitive-key masking, `build_subprocess_env` merge order (project-overrides-user-shared), OS allowlist accept/reject + case sensitivity, API user-env endpoints, `is_sensitive_key` false-positive rejection, venv bootstrap idempotency + partial-venv cleanup on failure, and `.env` parser cases.

---

## Follow-ups

- Per-project encryption key derivation (single key from settings for now).
- Audit log for env changes.
- Docker-based isolation (deferred).

## References

- Related: [[2026-06-08-project-environment]]
- External: [MNT-161 — Process environment (Linear)](https://linear.app/mnt/issue/MNT-161)
