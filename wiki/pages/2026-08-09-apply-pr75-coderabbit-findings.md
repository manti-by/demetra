---
title: Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int
date: 2026-08-09
type: implementation
status: resolved
session_id: -
services: [auth, api, database, runtime, wiki, react]
branch: code-review
tickets: []
tags: [code-review, coderabbit, auth, jwt, password-reset, react, env, wiki]
related: [2026-08-09-apply-code-review-findings, 2026-07-24-plain-auth-review-followups]
---

# Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int

## TL;DR

Applied all 5 open CodeRabbit findings on PR #75 ("Code review of release candidate"): added a per-user `password_version` so JWTs minted concurrently with a password reset are rejected after it commits (closes the snapshot race), handled `Request` inputs in `authFetch`/`authenticatedFetch` (method + `request.url` origin guard), rejected negative `env_get_int` defaults, passed `db_name` by name in `get_transaction`, and synced the Step 6 wiki doc with the `--porcelain=v1 -z` implementation. Migration `a4b5c6d7e8f9`; full suite 739 passed in 4.95s.

---

## Step 1 — MAJOR: password reset no longer leaves post-snapshot JWTs alive

**File:** demetra/services/auth/__init__.py:168; demetra/services/persistence/database.py:1061,1184; migration `a4b5c6d7e8f9`

`reset_password` snapshotted the user's JWTs *before* the transaction, while `save_jwt_token` runs in its own autocommitted transaction — a session minted after the snapshot survived the password change. Fix: versioned sessions instead of racing.

- New `users.password_version` and `jwt_tokens.password_version` columns (both `server_default=1`).
- `save_jwt_token` reads the user's current version at issuance and stores it on the token row.
- `update_user_password` bumps `password_version = password_version + 1` in the same statement.
- `verify_jwt_token` rejects any token whose stored version differs from the user's current version (a pre-reset token is always `< current`, so the reset invalidates it regardless of timing).

```python
# database.py — save_jwt_token
version_result = await connection.execute(
    text("SELECT password_version FROM users WHERE id = :user_id"),
    {"user_id": user_id},
)
...
# update_user_password
.values(password_hash=password_hash, password_version=users.c.password_version + 1)

# auth/__init__.py — verify_jwt_token
if user_data.get("password_version", 1) != token_data.get("password_version", 1):
    return None
```

Regression test `test_reset_password_rejects_token_minted_before_reset` re-inserts a token row with the old version after a reset and asserts `verify_jwt_token` returns `None`.

Note: `save_jwt_token` initially used `INSERT ... SELECT` but asyncpg rejected the doubled `:user_id` parameter (`AmbiguousParameterError: text versus character varying`); a fetch-then-insert with `RuntimeError` on a missing user row matches the persistence layer's existing error style.

## Step 2 — MAJOR: `authFetch`/`authenticatedFetch` handle `Request` inputs

**File:** react/src/services/api.ts:17,38

`RequestInfo` accepts a `Request`, but the origin guard derived the method only from `init` and passed the raw input to `assertTrustedOrigin` (`input.toString()` on a `Request` yields `[object Request]`, which resolved against `window.location.origin` and skipped the trusted-origin check). Now the method falls back to `request.method` and the guard receives `request.url`:

```ts
const request = input instanceof Request ? input : undefined;
const method = (init.method ?? request?.method ?? 'GET').toUpperCase();
if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
  assertTrustedOrigin(request?.url ?? input);
}
```

## Step 3 — MINOR: `env_get_int` rejects negative fallback defaults

**File:** demetra/services/runtime/utils.py:215

The docstring promised a nonnegative result, but a negative `default` was returned verbatim. `env_get_int` now raises `ValueError` when `default < 0`; all callers pass nonnegative defaults, so nothing breaks. Test: `test_env_get_int_rejects_negative_default`.

## Step 4 — TRIVIAL: named argument in `get_transaction`

**File:** demetra/services/persistence/database.py:152

`get_connection(db_name)` → `get_connection(db_name=db_name)` per the named-arguments guideline.

## Step 5 — MINOR: Step 6 wiki doc matches the porcelain implementation

**File:** wiki/pages/2026-08-09-apply-code-review-findings.md:110

The doc showed `-- "wiki/"` and "skipped the rename/copy destination record"; the implementation scopes `-- "wiki/" "AGENTS.md"` and *consumes the second NUL-delimited record* (`--porcelain=v1 -z` emits the destination first, source second). Prose and snippet updated.

## Test Results

- New tests: `test_auth.py` (stale-version token rejected after reset), `test_utils.py` (negative default rejected).
- Full suite: **739 passed in 4.95s** (was 737).
- Gates: `ruff check .`, `ty check`, `bandit`, React `tsc --noEmit` + `vite build` all pass.
- `alembic check` drift (users index/constraint, `session_history.length` comment) is pre-existing on the base commit and unrelated to `password_version`.

---

## Follow-ups

- Working tree is uncommitted on `code-review`; the orchestrator handles the commit/PR.
- Dev DB `alembic_version` was stamped `d1e2f3a4b5c6` (schema matched, version stale) before applying `a4b5c6d7e8f9`.

## References

- Related: [[2026-08-09-apply-code-review-findings]], [[2026-07-24-plain-auth-review-followups]]
- External: [manti-by/demetra#75](https://github.com/manti-by/demetra/pull/75)
