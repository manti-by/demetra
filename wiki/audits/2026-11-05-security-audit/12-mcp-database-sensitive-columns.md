# 12 — MCP `query_table` leaks `password_hash` and environment values

## Summary

- **Title:** Database inspection tool exposes password hashes and stored secrets
- **Problem:** The MCP `query_table` tool promises to strip sensitive fields, but
  `_filter_sensitive_columns` filters only an exact list of column names that does not
  include `password_hash`, `keys`, or key/value environment columns. Authentication
  password hashes (`users.password_hash`), encrypted API keys (`users.keys`), and
  plaintext `project_environment.value` entries survive and enter MCP responses.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-200** · **Category:** sensitive_data_exposure
- **CodeRabbit ID:** `5d987c95-dcbe-42bd-ace8-15cbf1be8f90`
- **Files (current):** `demetra/tools/database.py:17-35` (`SENSITIVE_COLUMNS`),
  `demetra/tools/database.py:247-256` (`_filter_sensitive_columns`),
  `demetra/tools/database.py:276-318` (`query_table`)
- **Revalidation:** Confirmed. `SENSITIVE_COLUMNS` has no `password_hash`/`keys`/
  `value`, and `query_table` returns `SELECT *` filtered only by that set. An existing
  `is_sensitive_key`/`ENCRYPTED_VALUE_MASK` policy (`demetra/library/models.py:255-279`)
  is not applied here.

## Steps

1. Extend `SENSITIVE_COLUMNS` (or switch to a per-table allowlist/projection) to
   exclude `password_hash`, `password_version`, `keys`, and any `*_hash`/`*_token`/
   `*_secret`/`*_key` column.
2. For `project_environment`/`user_environment` rows, mask `value` with
   `ENCRYPTED_VALUE_MASK` when `type == "encrypted"` **or** `is_sensitive_key(key)`,
   reusing `demetra.library.models.is_sensitive_key` (as the REST endpoints already do
   in `demetra/api/projects.py`).
3. Prefer table-specific safe output projections over `SELECT *` so future schema
   changes cannot reintroduce credential-bearing columns silently.
4. Add tests: querying `users` returns no `password_hash`/`keys`; querying
   `project_environment` masks encrypted and sensitive-key values.
