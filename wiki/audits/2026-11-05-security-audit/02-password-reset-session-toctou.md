# 02 — Password-reset TOCTOU survives session issuance

## Summary

- **Title:** Login issued during a concurrent password reset stays authenticated
- **Problem:** `login_with_password` verifies the old password against the hash read
  from the user snapshot, then yields at `is_email_allowed`. If a password reset
  commits in that window (revoking sessions and bumping `password_version`),
  `save_jwt_token` re-reads the *new* `password_version` from `users` and mints a
  session that matches it. The old-password login therefore survives the reset.
- **Date:** 2026-11-05
- **Severity:** medium · **CWE-367** · **Category:** broken_auth
- **CodeRabbit ID:** `dc600af9-0196-43b6-aa23-1c7bca116dc8`
- **Files (current):** `demetra/services/auth/sessions.py:158-176`,
  `demetra/services/persistence/database.py:1707-1750` (`save_jwt_token`)
- **Revalidation:** Confirmed. `save_jwt_token` still selects
  `SELECT password_version FROM users WHERE id = :user_id` at
  `database.py:1726-1727` rather than receiving the version captured at verification.

## Steps

1. Capture the verified password version in `login_with_password`
   (`demetra/services/auth/sessions.py:158`) from `user_data["password_version"]` (or
   `user_data.get("password_version", 1)`) immediately after the hash is verified.
2. Thread that value into `save_jwt_token` as an explicit `password_version` (or
   `expected_password_version`) argument, and store *that* value instead of re-reading
   `users.password_version`.
3. Reject issuance when the captured version no longer matches the current row (or
   re-read with `SELECT ... FOR UPDATE`) so a session minted across a reset is refused.
4. For the GitHub OAuth path (`authenticate_user`), pass the current version (no
   password reset applies) or a sentinel meaning "read current" to keep behaviour
   unchanged.
5. Add a concurrency regression test simulating a reset between password verification
   and `save_jwt_token`, asserting the minted token is rejected by
   `verify_jwt_token`.
