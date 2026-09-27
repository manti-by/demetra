---
title: MNT-192 Add edit button for env settings
date: 2026-08-31
type: implementation
status: resolved
session_id: mnt-192
services: [api, persistence, react]
branch: feature/mnt-192-add-edit-button-for-env-settings
tickets: [MNT-192]
tags: [env, frontend, encryption]
related:
- 2026-08-10-process-environment-3-layers-encryption-uv-venv.md
---

# MNT-192 Add edit button for env settings

## TL;DR

Added pencil edit button to every env var row in `EnvSettings` and `SharedEnvSettings` modals with inline edit, rename via delete+re-add, duplicate-key guard, sorted display, and backend preservation of encrypted values when blank is sent. Also fixed two data-loss paths (rename wiping secret, unchecking Encrypted on blank).

---

## Overview

Env screens only supported Add/Delete; editing required delete+re-add and encrypted values couldn't be changed (duplicate key rejected). Implemented MNT-192 across `demetra/services/persistence/database.py:1467`, `demetra/api/projects.py:244`, `react/src/utils/envFile.ts:1`, `react/src/components/EnvSettings.tsx:1`, `react/src/components/SharedEnvSettings.tsx:1`.

## Backend — preserve encrypted value on blank

When `env_type == "encrypted"` and `value == ""`, fetch existing row and reuse stored ciphertext instead of `encrypt_str("")`.

**File:** `demetra/services/persistence/database.py:1501` — same pattern for `upsert_project_environment` (`project_id`/`scope=="project"`) and `upsert_user_environment` (`user_id`/`scope=="user"`).

Also aligned project API validation with `demetra/api/users.py:17`: added `ENV_KEY_RE`, `MAX_ENV_KEY_LENGTH`, `MAX_ENV_VALUE_LENGTH`, key regex `[A-Za-z_][A-Za-z0-9_.-]*`, value limit 8192, NUL check.

## Frontend — shared validator

**File:** `react/src/utils/envFile.ts:24`

```ts
export const ENV_KEY_RE = /^[A-Za-z_][A-Za-z0-9_.-]*$/;
export const MAX_ENV_KEY_LENGTH = 128;
export function validateEnvKey(key: string): string | null { /* required, length, regex */ }
```

Both modals import it for Add and Edit.

## Frontend — edit mode + sorting

**Files:** `react/src/components/EnvSettings.tsx:45`, `react/src/components/SharedEnvSettings.tsx:34`

- `PencilIcon` + `editingKey: string | null` state; `sortByKey` + `sortedEntries` via `useMemo`; display uses `sortedEntries` (client-side only).
- `beginEdit(entry)`: sets `editingKey`, pre-fills `draftKey`, `draftValue=""` for encrypted (placeholder "leave blank to keep current value"), `draftEncrypted`.
- `cancelEdit()`, `handleSaveEdit()`: `validateEnvKey` + duplicate guard (`entry.key === newKey && entry.key !== editingKey`), `PUT` upsert; on rename upsert new key then delete old; placeholder switches when `isEditing && draftEncrypted`.
- `handleAddEntry`/`handleAddDraft` also use `validateEnvKey`, duplicate guard, sort after insert. Delete cancels edit if deleting edited row.

## Review fixes — secret preservation

Cursor PR review found two high-severity data-loss paths, both fixed:

- **Rename wiped secret:** blank-preservation lookup queried only new key (no row) → `encrypt_str("")` + delete old destroyed secret. Fix: `upsert_*_environment` accept `previous_key: str | None`; blank lookup tries current key then `previous_key`; duplicated blocks extracted into `_fetch_stored_encrypted_value`. API models `EnvironmentUpsert`/`ProjectEnvironmentUpsert` carry optional `previous_key`; `api.ts` upsert functions forward it; components send `editingKey`.
- **Unchecking Encrypted on blank overwrote secret with empty plaintext:** frontend `handleSaveEdit` now rejects save with "Enter a value to disable encryption" when encrypted entry has `draftEncrypted` off and blank value.

## Test Results

- `ruff` / `ty` / `pre-commit` — passed
- Full suite — 926 passed (incl. rename/blank-preservation and `previous_key` tests)

> **Consistency note (2026-09-02):** shared validation constants (`ENV_KEY_RE`, `MAX_ENV_KEY_LENGTH`, `MAX_ENV_VALUE_LENGTH`) now live in `demetra/library/env.py` and are imported by both API modules; frontend copy stays in `react/src/utils/envFile.ts`.

---

## Follow-ups

- None

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Ticket: https://linear.app/mnt/issue/MNT-192/add-edit-button-for-env-settings

> **Consistency note (2026-09-03):** Fixed `related` frontmatter — added `.md` extension to `2026-08-10-process-environment-3-layers-encryption-uv-venv.md`.
