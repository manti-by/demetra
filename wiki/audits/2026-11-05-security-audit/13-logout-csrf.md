# 13 — Logout has no CSRF / origin validation

## Summary

- **Title:** Cross-site form can sign a victim out
- **Problem:** `do_logout` revokes the session presented by the ambient `auth_token`
  cookie without verifying the request origin or requiring an anti-CSRF token. With
  cross-site cookies enabled (`COOKIE_SAMESITE=none`), an attacker page can submit a
  form that deletes the victim's server-side session.
- **Date:** 2026-11-05
- **Severity:** low · **CWE-352** · **Category:** csrf
- **CodeRabbit ID:** `3cc689e3-4ed4-44cd-9a81-c50d672e9e63`
- **Files (current):** `demetra/api/auth.py:119-135` (`do_logout`)
- **Revalidation:** Confirmed. No `Origin`/`Referer` check and no anti-CSRF token.
  Default `COOKIE_SAMESITE` is `lax` (which blocks cross-site POST attachment), so the
  practical risk depends on `COOKIE_SAMESITE=none`.

## Steps

1. In `do_logout`, validate the `Origin` (or `Referer`) header against the trusted
   application origins (`CORS_ALLOWED_ORIGINS` from `demetra/settings.py`) before
   calling `logout`.
2. Alternatively require an anti-CSRF token for the logout mutation, or set the cookie
   `SameSite` to `strict` for session-mutating endpoints.
3. Apply the origin check unconditionally so that a future `COOKIE_SAMESITE=none`
   configuration is still protected.
4. Add tests: logout with a missing/foreign `Origin` is rejected; a trusted origin
   succeeds.
