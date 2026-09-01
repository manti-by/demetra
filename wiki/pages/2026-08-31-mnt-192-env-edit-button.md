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
related: [2026-08-10-process-environment-3-layers-encryption-uv-venv]
---

# MNT-192 Add edit button for env settings

## TL;DR

Added an edit (pencil) button to every env var row in both `EnvSettings` (project) and `SharedEnvSettings` (user-shared) modals, with inline edit mode, rename via delete+re-add, duplicate-key guard, sorted display, and backend preservation of encrypted values when a blank value is sent.

---

## Overview

Environment screens only supported Add/Delete. Changing a value required delete+re-add, and encrypted values could not be changed at all (Add rejected duplicate keys). This implements MNT-192.

**Files:** `demetra/services/persistence/database.py:1467`, `demetra/api/projects.py:244`, `react/src/utils/envFile.ts:1`, `react/src/components/EnvSettings.tsx:1`, `react/src/components/SharedEnvSettings.tsx:1`

## Step 1 — Backend: preserve encrypted value on blank upsert

**Problem:** Editing an encrypted var shows a blank value field with hint "leave blank to keep current value". Submitting blank must not overwrite the stored encrypted secret with an empty encryption.

**Fix:** In both `upsert_project_environment` and `upsert_user_environment`, when `env_type == "encrypted"` and `value == ""`, fetch the existing row; if it exists and is encrypted, reuse its stored (already-encrypted) value instead of `encrypt_str("")`.

**File:** `demetra/services/persistence/database.py:1501`

```python
if env_type == "encrypted" and value == "":
    async with get_connection() as connection:
        existing = await connection.execute(
            select(project_environments.c.value, project_environments.c.type).where(
                (project_environments.c.project_id == project_id)
                & (project_environments.c.key == key)
                & (project_environments.c.scope == "project")
            )
        )
        row_existing = existing.fetchone()
        if row_existing is not None and row_existing.type == "encrypted":
            stored_value = row_existing.value
        else:
            stored_value = encrypt_str(value)
```

Same pattern for `upsert_user_environment` scoped to `user_id`/`scope == "user"`.

Also aligned project API validation with user API:

**File:** `demetra/api/projects.py:12`

- Added `ENV_KEY_RE`, `MAX_ENV_KEY_LENGTH`, `MAX_ENV_VALUE_LENGTH`
- Validates key length, regex `[A-Za-z_][A-Za-z0-9_.-]*`, value length 8192, NUL bytes — matching `demetra/api/users.py:17`.

## Step 2 — Frontend: shared key validator

**File:** `react/src/utils/envFile.ts:24`

```ts
export const ENV_KEY_RE = /^[A-Za-z_][A-Za-z0-9_.-]*$/;
export const MAX_ENV_KEY_LENGTH = 128;
export function validateEnvKey(key: string): string | null {
  const trimmed = key.trim();
  if (!trimmed) return "Environment key is required";
  if (trimmed.length > MAX_ENV_KEY_LENGTH) return "Environment key must be at most 128 characters";
  if (!ENV_KEY_RE.test(trimmed)) return "Environment key must match [A-Za-z_][A-Za-z0-9_.-]*";
  return null;
}
```

Both modals import `validateEnvKey` and use it for Add and Edit.

## Step 3 — Frontend: edit mode + sorting in both modals

**Files:** `react/src/components/EnvSettings.tsx:45`, `react/src/components/SharedEnvSettings.tsx:34`

* Added `PencilIcon` component and `editingKey: string | null` state.
* Added `sortByKey` helper and `sortedEntries` via `useMemo`; fetch sorts on load and every mutation re-sorts (`sortByKey([...prev, entry])`). Display uses `sortedEntries`, so rows appear sorted by name ascending client-side only (backend order untouched).
* `beginEdit(entry)`: sets `editingKey`, pre-fills `draftKey` with current key, `draftValue` with `""` for encrypted (blank + placeholder "leave blank to keep current value") else current value, `draftEncrypted` from `entry.type`.
* `cancelEdit()`: clears edit state and draft.
* `handleSaveEdit()`: validates via `validateEnvKey`, duplicate guard (`entry.key === newKey && entry.key !== editingKey`), then `PUT` to `upsert...`. On rename (`newKey !== editingKey`) does `upsert(newKey)` then `delete(oldKey)` and merges state; otherwise maps entry. Resets edit state on success.
* `handleAddEntry` / `handleAddDraft` now also use `validateEnvKey` and duplicate guard, and sort after insert.
* Value input placeholder switches to "leave blank to keep current value" when `isEditing && draftEncrypted`.
* Delete also cancels edit if deleting the edited row.

## Test Results

* `ruff check` — All checks passed
* `ty check` — All checks passed
* `pytest tests/test_database.py tests/test_api.py` — 122 passed
* `react npm run test` — 9 files, 58 passed
* Full suite — 919 passed (1 flaky duplicate-email in `test_user_env_is_isolated_between_users` passes on rerun)

---

## Follow-ups

- None

## References

- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Ticket: https://linear.app/mnt/issue/MNT-192/add-edit-button-for-env-settings
