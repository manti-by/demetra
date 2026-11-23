---
title: Password Hashing, Cookie & CORS Hardening, and Dependency Bump
generated: {by: demetra, at: '2026-08-03T00:00:00Z'}
description: 'Records auth hardening — replacing passlib with direct bcrypt, making the auth-cookie SameSite and CORS origins environment-driven instead of hardcoded or wildcard, and bumping to 1.15.5 with a dependency refresh — committed as 5bcce84 via PR #67 with 545 tests passing.'
type: implementation
status: stable
session_id: '-'
services: [auth, main, settings, api, react, database, watcher]
branch: master
tickets: [MNT-148, MNT-50, MNT-48, MNT-156, MNT-81, MNT-86]
tags: [auth, security, bcrypt, cors, cookies, dependencies, jwt, passwords, csrf, origin-validation, websockets, ownership]
related: [2026-08-19-split-auth-linear-services-and-review-failure-handling.md, 2026-07-24-plain-auth-review-followups.md, 2026-08-03-check-api-auth-and-credentials.md]
---

# Password Hashing, Cookie & CORS Hardening, and Dependency Bump

## TL;DR

Replaced `passlib` `CryptContext` wrapper with direct `bcrypt` (dropped `passlib[bcrypt]`), made auth-cookie `SameSite` and CORS origins env-driven instead of hardcoded/wildcard, and bumped to `1.15.5` with broad dependency refresh. All gated at 545 tests. Committed as `5bcce84` via PR #67.

> **Status (2026-08-23):** Merged long ago; subsequent hardening in [2026-08-19-split-auth-linear-services-and-review-failure-handling](/pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md). "Not yet committed" framing below is historical.

## Step 1 — Replace passlib with direct bcrypt

`passlib` is unmaintained wrapper over same `bcrypt` lib; removed indirection.

**`demetra/services/passwords.py`:**

```python
# before: CryptContext(schemes=["bcrypt"]); _PCTX.hash(secret=plain) / verify
# after:  import bcrypt
bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
```

Both verify `$2b$` hashes — no migration needed. `_validate_password` still guards both paths. `verify_password` also catches `ValueError` (malformed hash) + `UnicodeEncodeError` (non-ASCII) → `False` (fail-closed).

**`pyproject.toml`:** removed `passlib[bcrypt]>=1.7.4,<1.8`, added `bcrypt>=4.1.3,<4.2` (later `5.0.0`).

## Step 2 — Configurable cookie SameSite

**`demetra/settings.py`:**

```python
def get_cookie_samesite() -> CockieSamesite:
    value = os.environ.get("COOKIE_SAMESITE", "lax").lower()
    if value not in {"lax","strict","none"}: return "lax"
    if value == "none" and not COOKIE_SECURE: raise SettingsError(...)
    return value
COOKIE_SAMESITE = get_cookie_samesite()  # now get_cookie_samesite(is_cockie_secure=COOKIE_SECURE)
```

**`demetra/api/auth.py:37`** + **`demetra/api/github.py:76`** — `samesite=COOKIE_SAMESITE` replaces literal `"lax"` on `auth_token`. `github.py:31` keeps `oauth_state` at `lax` (must survive cross-site redirect; `strict` would block it).

## Step 3 — Explicit CORS allowlist

Was `allow_origins=["*"]` + `allow_credentials=True` — unsafe. Restricted via env.

**`demetra/app.py`:** `allow_origins=CORS_ALLOWED_ORIGINS` (was `["*"]`).

**`demetra/settings.py`:** `CORS_ALLOWED_ORIGINS` from `CORS_ALLOWED_ORIGINS` env (default `localhost:5173,localhost:8000`), via `env_get_list()`, `*` rejected at startup (`SettingsError` — Starlette forbids wildcard with credentials).

## Step 4 — Deps, version, pre-commit, release command

- `pyproject.toml` `1.15.5`, `uv-bump` refresh (aiohttp 3.14.3, fastapi 0.141.1, `mcp>=2.0.0`, `redis>=8.1.0`, etc.), `.pre-commit-config.yaml` ruff `v0.15.21`→`v0.16.1`, `uv.lock` regenerated.
- `.opencode/commands/release-name.md` (now skill) — two-word space-themed codenames.

## Test Results

`ruff`, `ty`, `bandit`, `pre-commit`, 545 tests pass.

## Source — [2026-07-24-plain-auth-review-followups](/archive/2026-07-24-plain-auth-review-followups.md)

Password auth (MNT-148, 2026-07-24): bcrypt via `demetra/services/auth/passwords.py` (`hash_password`/`verify_password`, rejects empty/<8 chars/>72-byte), `signup_with_password`/`login_with_password`/`reset_password` in the `auth/` subpackage, JWT cookie endpoints `POST /auth/signup|login|logout`, the `--resetpass` CLI, and the `users` migration (nullable `password_hash`/`github_id`, unique email, CHECK `password_hash IS NOT NULL OR github_id IS NOT NULL`, GitHub emails backfilled as `gh-<id>@github.local`). Review hardening: token cookie-only (removed from JSON body), email normalization `strip().lower()` + `IntegrityError` race guard, named-argument helper calls, a11y labels. Originally decided in [2026-07-24-plain-auth-review-followups](/archive/2026-07-24-plain-auth-review-followups.md).

## Source — [2026-08-03-check-api-auth-and-credentials](/archive/2026-08-03-check-api-auth-and-credentials.md)

API auth tightening (MNT-156, 2026-08-03): shared `Depends(get_current_user_dep)` replaced ~10 hand-rolled cookie checks (consistent 401 contract across routers); session lookups are user-scoped (`get_session_id_by_task_id(task_id, user_id)`; the watcher verifies ownership before streaming); WebSocket rejections deliver close codes via accept-then-close (`reject_connection`: 4001 no token, 4003 forbidden, 4000 invalid task_id/log path, 4004 session not found); React `authenticatedFetch` adds `credentials:'include'` on every request and runs `assertTrustedOrigin` before credentialed mutations. Originally decided in [2026-08-03-check-api-auth-and-credentials](/archive/2026-08-03-check-api-auth-and-credentials.md).

## Follow-ups

- Verify login with `COOKIE_SAMESITE`/`COOKIE_SECURE`/`CORS_ALLOWED_ORIGINS` in deployment.

> **Consistency (2026-08-27):** `demetra/services/passwords.py` → `demetra/services/auth/passwords.py` (commit `04436c6`). Logic unchanged.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [2026-07-24-plain-auth-review-followups](/archive/2026-07-24-plain-auth-review-followups.md), [2026-08-19-split-auth-linear-services-and-review-failure-handling](/pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md)

> **Consistency note (2026-11-11, Consistency Agent):** The `CORS_ALLOWED_ORIGINS` default quoted above is now the explicit-scheme list `["http://localhost:5173", "http://localhost:8000"]` (`demetra/settings.py:248`), and `bcrypt` is pinned at `5.0.0`. The `get_cookie_samesite(is_cockie_secure=COOKIE_SECURE)` typo in `demetra/settings.py:253` is still present in the source.
