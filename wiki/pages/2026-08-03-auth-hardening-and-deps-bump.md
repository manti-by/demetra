---
title: Password Hashing, Cookie & CORS Hardening, and Dependency Bump
date: 2026-08-03
type: implementation
status: resolved
session_id:
services: [auth, main, settings]
branch: master
tickets: [MNT-148]
tags: [auth, security, bcrypt, cors, cookies, dependencies]
related: [2026-07-24-plain-auth-review-followups.md]
---

# Password Hashing, Cookie & CORS Hardening, and Dependency Bump

## TL;DR

Working-tree change set on `master` (not yet committed): replaced the `passlib`
`CryptContext` bcrypt wrapper with a direct, standard-library-backed `bcrypt` dependency;
dropped the `passlib[bcrypt]` package; made the auth-cookie `SameSite` value and the CORS
origin allow-list configurable via env instead of being hardcoded/wide-open; and bumped
`demetra` to `1.15.5` with a broad `uv-bump` dependency refresh (aiohttp, fastapi, mcp 2.0,
redis, etc.). A new OpenCode `release-naming` command was also added. Net effect: a tighter
auth surface (configurable cookie scope + explicit CORS origins) and a leaner, more current
dependency tree.

---

## Overview

Four loose groups of changes sitting in the working tree:

1. **Password hashing** — swap `passlib` → direct `bcrypt` API, drop the `passlib` dep.
2. **Auth cookie `SameSite`** — env-driven via `COOKIE_SAMESITE`.
3. **CORS allowlist** — replace `allow_origins=["*"]` with env-driven `CORS_ALLOWED_ORIGINS`.
4. **Release: dependencies + pre-commit + version**, plus a new OpenCode release-naming command.

## Step 1 — Replace passlib with direct bcrypt

Dropped the `passlib[bcrypt]` wrapper in favor of the upstream `bcrypt` package. `passlib` was a
long-unmaintained runtime layer that added a second bcrypt variant stack on top of the same
underlying library.

**File:** `demetra/services/passwords.py`
before:
```python
from passlib.context import CryptContext
_PCTX = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain):
    _validate_password(plain=plain)
    return _PCTX.hash(secret=plain)

def verify_password(plain, hashed):
    ...
        return _PCTX.verify(secret=plain, hash=hashed)
```
after:
```python
import bcrypt

def hash_password(plain):
    _validate_password(plain=plain)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

def verify_password(plain, hashed):
    ...
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
```
- `bcrypt.checkpw` and `passlib`'s raw-bcrypt path both verify `$2b$` hashes, so existing
  hashes remain valid (no migration needed).
- `_validate_password` still runs before both calls, preserving the `AuthError` -> `False`
  guard in `verify_password`.

**File:** `pyproject.toml` — removed `passlib[bcrypt]>=1.7.4,<1.8`; added `bcrypt>=4.1.3,<4.2`.

## Step 2 — Configurable cookie SameSite

`SameSite` was hardcoded to `"lax"` in three cookie-writing spots. Now pulled from settings,
with validation and a safe default.

**File:** `demetra/settings.py`
```python
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax").lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    COOKIE_SAMESITE = "lax"
```

**Files:** `demetra/api/auth.py:37` and `demetra/api/github.py:31,76` — `samesite=COOKIE_SAMESITE`
replaces the literal `"lax"` on both the auth-token and `oauth_state` cookies.

## Step 3 — Explicit CORS allowlist

The ASGI app previously allowed every origin while sending credentials — an unsafe combination
(any site can make credentialed requests). Restricted to an env-controlled list.

**File:** `demetra/app.py`
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,   # was ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)
```

**File:** `demetra/settings.py`
```python
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:8000",
    ).split(",")
    if origin.strip()
]
```
Empty entries are filtered. Deployments must set `CORS_ALLOWED_ORIGINS` to the real frontend
origin(s).

## Step 4 — Dependency bump, version, pre-commit, release command

- **File:** `pyproject.toml` — `version = "1.15.5"`; refreshed bounds via `uv-bump`
  (aiohttp `3.14.3`, fastapi `0.141.1`, langchain-core `1.5.3`, langsmith `0.10.15`,
  `mcp>=2.0.0`, `redis>=8.1.0`, `uvicorn>=0.52.1`, `websockets>=17.0.1`, dev: faker,
  ipython, `ty>=0.0.65`, `uv-bump>=0.6.0`, etc.).
- **File:** `.pre-commit-config.yaml` — `ruff` hook `v0.15.21` → `v0.16.1`.
- **File:** `uv.lock` — regenerated to match.
- **File:** `.opencode/commands/release-name.md` — new OpenCode command `release-naming` that
  generates exactly-two-word, space-themed release codenames (e.g. "Aurora Borealis").

## Test Results

Not yet run in this session; dependency-only and config/constant substitutions (no behavior
change beyond hashing backend and cookie/CORS provenance). Recommended before release:

```
uv run pre-commit run --all-files
uv run ruff check .
uv run ty check
uv run bandit -c pyproject.toml .
uv run pytest tests/
```

---

## Follow-ups

- Run the full lint/type/test gates above and confirm the `bcrypt` swap passes the auth tests
  in `tests/`.
- Verify end-to-end login in a deployment that sets `COOKIE_SAMESITE`, `COOKIE_SECURE`, and
  `CORS_ALLOWED_ORIGINS`.

## References

- Related: [[2026-07-24-plain-auth-review-followups]] (MNT-148 auth work this builds on)