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
related: [2026-03-05-github-login.md, 2026-03-05-github-login-react-app.md, 2026-07-22-react-frontend-template-warp.md, 2026-08-03-auth-hardening-and-deps-bump.md, 2026-08-06-allowlist-review-fixes.md]
---

# Plain Password Auth Implementation and Review Follow-ups

## TL;DR

Implemented bcrypt password auth (signup/login/logout) alongside GitHub OAuth with JWT cookies and a React form. Two CodeRabbit passes hardened it: removed token from JSON body (cookie-only), email normalization, `--resetpass` CLI, DB email backfill migration, a11y fixes, named-argument hardening, `verify_password` policy, structured CLI error handling, and unified Header display-name.

## Overview

Complete password path spanning `services/passwords.py` (bcrypt via passlib, later direct bcrypt), `services/auth.py`, `api/auth.py`, migration, and `PasswordAuthForm.tsx`. Two review passes on same branch.

## Step 1 — Backend

**`demetra/services/passwords.py`:**

```python
_PCTX = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(plain): _validate_password(plain=plain); return _PCTX.hash(secret=plain)
def verify_password(plain, hashed):
    if not plain: return False
    try: _validate_password(plain=plain); return _PCTX.verify(secret=plain, hash=hashed)
    except AuthError: return False
```

Rejects empty / <8 char / >72-byte passwords.

**`demetra/services/auth.py`:** `signup_with_password` (validate, check uniqueness, hash, JWT), `login_with_password`, `reset_password` (follow-up).

**`demetra/api/auth.py`:** `POST /auth/signup|login|logout` — sets/clears `auth_token` cookie.

## Step 2 — Migration

**`migrations/versions/b1c2d3e4f5a6_add_users_password_hash_and_nullable_oauth_fields.py`** — adds nullable `password_hash`, makes `github_id`/`github_username` nullable, unique index on `email`, partial unique on `github_id` where not null, CHECK `password_hash IS NOT NULL OR github_id IS NOT NULL`. Backfills null emails as `gh-<github_id>@github.local` before NOT NULL.

## Step 3 — React

`PasswordAuthForm.tsx` (login/signup toggle, validation), `services/api.ts` (`signup`/`loginWithPassword`/`logout` with `credentials:'include'`), `App.css` (`.password-auth-form` etc.).

## Step 4 — First-pass review fixes

- **Cookie-only auth:** removed `token` from JSON body, `AuthResponse`, `PasswordAuthForm` localStorage write.
- **Email normalization + race guard:** `strip().lower()` + `try/except IntegrityError` on signup/login.
- **Password reset CLI:** `main.py --resetpass` → `reset_password_cli()` (interactive), `database.py:update_user_password`, `auth.py:reset_password`.
- **Verify short-circuit:** `verify_password` returns `False` on empty (superseded in pass 2).
- **A11y:** `aria-label` on inputs, `role="alert"` on error.
- **Migration:** backfill NULL emails for GitHub users.

## Step 5 — Second-pass review fixes (on `86712f4`)

- **Password helpers:** all calls use named args (`plain=plain`, `secret=plain`, `hash=hashed` — passlib's real param names per `inspect.signature`). `verify_password` re-validates before `verify` and catches `AuthError`.
- **CLI error handling:** `init_db()` inside try/except; catches `AuthError`/`SQLAlchemyError` separately, redacts email in success message, returns `int` → `sys.exit()`.
- **Header fallback:** `displayName = user?.github_username ?? user?.email ?? "User"` for avatar + name (email-only users get initial).
- **Wiki metadata:** fixed `related` frontmatter, fence language `python`.

## Step 6 — Tests

- `tests/test_passwords.py` (9) — hash properties, rejection of empty/short/long, verify.
- `tests/test_auth_password_api.py` (8) — signup/login/logout mocked.
- `tests/test_auth.py` — extended.

## Source — [[2026-03-05-github-login]]

GitHub OAuth on FastAPI (`login`/`logout`/`current-user`, `services/auth.py` JWT) — MNT-48, 2026-03-05. MNT-148 added password path beside it; later [[2026-08-03-auth-hardening-and-deps-bump]] replaced passlib with direct bcrypt.

## Source — [[2026-03-05-github-login-react-app]]

React wiring of GitHub button via `AuthContext` — MNT-50, 2026-03-05. Origin of Header/AuthContext refined in Step 5.

## Follow-ups

- All review feedback applied; historical notes: passlib→bcrypt, `SameSite`/`CORS` hardening, token still returned on GitHub callback (`AuthResponse.token?`).
- **Module paths (2026-08-07, `04436c6`):** `services/auth.py` → `auth/__init__.py` + `auth/sessions.py|jwt.py|oauth.py|copy.py`, `services/passwords.py` → `auth/passwords.py`.

## References

- Linear: MNT-148
- Related: [[2026-07-22-react-frontend-template-warp]], [[2026-08-03-auth-hardening-and-deps-bump]], [[2026-08-06-allowlist-review-fixes]]
