---
title: Plain Password Auth Implementation and Review Follow-ups
date: 2026-07-24
type: implementation
status: resolved
session_id: mnt-148-plain-auth
services: [auth, api, database, react]
branch: mnt-148-plain-auth
tickets: [MNT-148, MNT-50, MNT-48]
tags: [auth, passwords, jwt, cookies, accessibility, github, oauth, react]
related: [2026-07-22-react-frontend-template-warp, 2026-08-03-auth-hardening-and-deps-bump, 2026-08-06-allowlist-review-fixes, 2026-03-05-github-login-react-app, 2026-03-05-github-login]
---

# Plain Password Auth Implementation and Review Follow-ups

## TL;DR

Implemented password-based signup/login/logout alongside existing GitHub OAuth,
with bcrypt password hashing, JWT cookie-based sessions, and a React auth form.
Two passes of review follow-ups removed the token from the JSON response body
(cookie-only), added email normalization, a `--resetpass` CLI command,
database-level email migration for existing GitHub-only users, accessibility
improvements, named-argument calls in the password helpers, hardened
`verify_password` policy, structured CLI error handling, and a unified Header
display-name fallback chain.

---

## Overview

MNT-148 added a complete password authentication path to complement the existing
GitHub OAuth flow. The implementation spans the backend (FastAPI endpoints, auth
service, database layer, migration) and frontend (React form, API client). Two
passes of CodeRabbit review follow-ups refined the API surface, hardened edge
cases, and cleaned up the implementation.

## Step 1 — Backend auth service and endpoints

Added `demetra/services/passwords.py` with bcrypt hashing via passlib, and
extended `demetra/services/auth.py` with `signup_with_password` and
`login_with_password` — both issue JWT tokens and persist them in the
`jwt_tokens` table.

`demetra/services/auth.py`:

- `signup_with_password`: validates email format, checks uniqueness, hashes
  password, creates user, issues JWT token
- `login_with_password`: looks up user by email, verifies password hash,
  issues JWT token
- `reset_password`: looks up user by email, updates password hash (added
  in follow-up pass)

**File:** `demetra/services/passwords.py`

```python
_PCTX = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    _validate_password(plain=plain)
    return _PCTX.hash(secret=plain)

def verify_password(plain: str, hashed: str) -> bool:
    if not plain:
        return False
    try:
        _validate_password(plain=plain)
        return _PCTX.verify(secret=plain, hash=hashed)
    except AuthError:
        return False
```

Validation rejects empty, <8 char, and >72 byte passwords.

**File:** `demetra/api/auth.py` — Three endpoints:

- `POST /api/v1/auth/signup` — creates account, sets `auth_token` cookie
- `POST /api/v1/auth/login` — authenticates, sets `auth_token` cookie
- `POST /api/v1/auth/logout` — deletes JWT token, clears cookie

## Step 2 — Database migration

**File:**
`migrations/versions/b1c2d3e4f5a6_add_users_password_hash_and_nullable_oauth_fields.py`

Adds `password_hash` column (nullable), makes `github_id` and
`github_username` nullable, adds a unique index on `email`, a partial unique
index on `github_id` (where not null), and a CHECK constraint ensuring every
user has at least one auth method (`password_hash IS NOT NULL OR github_id IS
NOT NULL`).

For existing GitHub-only users with NULL email, the migration sets:
`email = 'gh-' || github_id || '@github.local'` before applying the NOT NULL
constraint.

## Step 3 — React frontend

**File:** `react/src/components/PasswordAuthForm.tsx` — New component with
login/signup toggle, form validation, and error display.

**File:** `react/src/services/api.ts` — Added `signup`, `loginWithPassword`,
`logout` functions using `credentials: 'include'` for cookie-based auth.

**File:** `react/src/App.css` — Added `.password-auth-form`, `.auth-field`,
`.auth-submit`, `.auth-error`, `.auth-toggle`, `.auth-divider` styles.

## Step 4 — First-pass review follow-ups

Changes on top of the initial MNT-148 commit, applied to the same branch:

### Cookie-only auth
- **File:** `demetra/api/auth.py` — Removed `token` from JSON response body.
- **File:** `react/src/services/api.ts` — Removed `token` from `AuthResponse` interface.
- **File:** `react/src/components/PasswordAuthForm.tsx` — Removed
  `localStorage.setItem('auth_token', response.token)` — auth is now
  cookie-only.
- **File:** `tests/test_auth_password_api.py` — Tests still check the cookie
  but no longer expect `token` in response body.

### Email normalization and race-condition guard
- **File:** `demetra/services/auth.py` — `signup_with_password` and
  `login_with_password` now strip and lowercase email input. Added
  `try/except IntegrityError` as a second line of defense against concurrent
  duplicate signup.

### Password reset CLI
- **File:** `main.py` — Added `--resetpass` flag that runs
  `reset_password_cli()`, prompting for email and new password interactively.
- **File:** `demetra/services/database.py` — Added `update_user_password`
  function.
- **File:** `demetra/services/auth.py` — Added `reset_password` async
  function.

### Verify password short-circuit
- **File:** `demetra/services/passwords.py` — `verify_password` returns
  `False` for empty plain text instead of calling `_validate_password`
  (which would raise). Prevents crash on missing/empty password during login.
  (Superseded in the second pass — see Step 5.)

### Accessibility
- **File:** `react/src/components/PasswordAuthForm.tsx` — Added `aria-label`
  to email and password inputs, `role="alert"` on error message.

### Migration fix
- **File:** Migration file — Added `UPDATE users SET email = ...` SQL to
  backfill NULL emails for existing GitHub users before applying NOT NULL
  constraint.

## Step 5 — Second-pass review follow-ups

A second CodeRabbit review surfaced four additional items, addressed in this
session on top of commit `86712f4`.

### Password helper hardening
- **File:** `demetra/services/passwords.py` — All internal calls now use named
  arguments: `_validate_password(plain=plain)`,
  `_PCTX.hash(secret=plain)`, `_PCTX.verify(secret=plain, hash=hashed)`.
  `verify_password` now re-validates the plain-text password before calling
  `_PCTX.verify` and catches `AuthError` to return `False`, enforcing the same
  72-byte UTF-8 policy as `hash_password` without raising on the login path.
  The empty-password short-circuit is preserved.

### CLI reset error handling
- **File:** `main.py` — `reset_password_cli` moves `init_db()` inside the
  try/except boundary so database initialization failures receive the same
  formatted handling as reset failures. Catches `AuthError` and
  `SQLAlchemyError` separately with a `Database error: ...` message. The
  success message no longer includes the raw email address (redacted to
  `"Password reset successfully"`). The function now returns `int` and the
  caller propagates it through `sys.exit()`, so `--resetpass` exits non-zero
  on failure.

### Header fallback chain
- **File:** `react/src/components/Header.tsx` — Introduced a shared
  `displayName` (`user?.github_username ?? user?.email ?? "User"`) and used
  it for both the avatar initial and the user name display. Email-only users
  now get a non-empty initial.

### Wiki metadata
- **File:** `wiki/pages/2026-07-24-plain-auth-review-followups.md` — Added
  `2026-07-22-react-frontend-template-warp` to the frontmatter `related`
  field to match the existing body cross-link, and tagged the Python code
  fence explicitly as `python` (was a bare fence, flagged by markdownlint).
  Updated the embedded code example to match the new `passwords.py` content.

### Note on the named-argument fix
The review suggested `plain=plain` and `hashed=hashed` for the passlib calls,
but passlib's actual parameter names are `secret` and `hash` (verified with
`inspect.signature(ctx.hash)` and `inspect.signature(ctx.verify)`). The fix
uses the library's real keyword names, which satisfies the AGENTS.md
"named-args-only" rule without lying to the type checker or LSP.

## Step 6 — Tests

**New file:** `tests/test_passwords.py` (9 tests) — Hash properties,
rejection of empty/short/long passwords, verify correctness.

**New file:** `tests/test_auth_password_api.py` (8 tests) — API-level tests
for signup, login, logout endpoints using mocked services.

**Updated:** `tests/test_auth.py` — Extended tests for password auth flow.

---

## Source — [[2026-03-05-github-login]]

Originally added in [[2026-03-05-github-login]] on 2026-03-05 (MNT-48): **GitHub OAuth
login** on the FastAPI backend. Endpoints `login`/`logout`/`current-user`, GitHub OAuth
flow in `demetra/services/auth.py`, JWT token services, and README setup docs. MNT-148
added the password path beside this OAuth path, and later auth hardening
([[2026-08-03-auth-hardening-and-deps-bump]]) replaced passlib with direct bcrypt —
GitHub OAuth remains a supported auth path. The frontend `AuthContext` / cookie handling
described in this page traces back to the MNT-48 JWT-cookie integration.

## Source — [[2026-03-05-github-login-react-app]]

Originally added in [[2026-03-05-github-login-react-app]] on 2026-03-05 (MNT-50): the
React app wired the GitHub sign-in button (via `AuthContext`) to the FastAPI auth
endpoints. The header shows a greeting with the logged-in user or a sign-in prompt,
and a loading indicator while the auth state resolves — the origin of the `Header`
display-name and `AuthContext` this page's Step 5 header-fallback work refines.

## Follow-ups

- None — all review feedback applied across two passes on the same branch.
- _Historical note (2026-08-03):_ the `passlib`-based `passwords.py` shown above was
  replaced with a direct `bcrypt` API, the auth-cookie `SameSite` was made env-driven
  (`COOKIE_SAMESITE`), and the CORS origins were restricted via `CORS_ALLOWED_ORIGINS` —
  see [[2026-08-03-auth-hardening-and-deps-bump]] for the current state.
- _Review-fix note (2026-08-03):_ the auth hardening was further tightened after review —
  `verify_password` now fails closed on malformed/non-ASCII stored hashes, the `oauth_state`
  cookie is pinned to `SameSite=lax` so the GitHub redirect still works under `strict`,
  `CORS_ALLOWED_ORIGINS=*` is rejected, and `COOKIE_SAMESITE=none` requires `COOKIE_SECURE=true`.
  See [[2026-08-03-auth-hardening-and-deps-bump]].

## References

- Linear: MNT-148
- Related: [[2026-07-22-react-frontend-template-warp]] (auth context component), [[2026-08-03-auth-hardening-and-deps-bump]] (subsequent hardening that replaces passlib)
