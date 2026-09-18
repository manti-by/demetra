---
title: "Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int"
date: 2026-08-09
type: implementation
status: resolved
session_id: "-"
services: [auth, api, database, runtime, wiki, react]
branch: code-review
tickets: []
tags: [code-review, coderabbit, auth, jwt, password-reset, react, env, wiki]
related:
- 2026-08-09-apply-code-review-findings.md
- 2026-07-24-plain-auth-review-followups.md
---

# Apply CodeRabbit findings — PR #75 password reset, Request fetch, env_get_int

## TL;DR

Applied 5 CodeRabbit findings on PR #75: versioned JWTs via `password_version` to close the post-snapshot race, fixed `Request`-aware `authFetch` origin guard, rejected negative `env_get_int` defaults, named `db_name` arg in `get_transaction`, and synced wiki docs to `--porcelain=v1 -z`. Migration `a4b5c6d7e8f9`; 739 passed in 4.95s.

---

## Step 1 — MAJOR: password reset race via `password_version`

**Files:** `demetra/services/auth/__init__.py:168`, `demetra/services/persistence/database.py:1061,1184`, migration `a4b5c6d7e8f9`

`reset_password` snapshotted JWTs before its transaction; `save_jwt_token` runs in a separate autocommit — a session minted after the snapshot survived reset.

- New columns `users.password_version` + `jwt_tokens.password_version` (`server_default=1`).
- `save_jwt_token` stores user's current version on the token row.
- `update_user_password` bumps `password_version + 1` atomically.
- `verify_jwt_token` rejects mismatched versions.

```python
# save_jwt_token: fetch version then insert
# update_user_password: .values(password_version=users.c.password_version + 1)
# verify_jwt_token: if user_version != token_version: return None
```

Test `test_reset_password_rejects_token_minted_before_reset` re-inserts old-version token and asserts rejection. Note: `INSERT ... SELECT` with doubled `:user_id` hit `AmbiguousParameterError` on asyncpg; fetch-then-insert used instead.

## Step 2 — MAJOR: `authFetch` handles `Request` inputs

**File:** `react/src/services/api.ts:17,38`

`RequestInfo` accepts `Request`; method was derived only from `init` and `input.toString()` on `Request` gave `[object Request]`, skipping the trusted-origin check.

```ts
const request = input instanceof Request ? input : undefined;
const method = (init.method ?? request?.method ?? 'GET').toUpperCase();
if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS')
  assertTrustedOrigin(request?.url ?? input);
```

## Step 3 — MINOR: `env_get_int` rejects negative defaults

**File:** `demetra/services/runtime/utils.py:215` — now raises `ValueError` if `default < 0`. Test: `test_env_get_int_rejects_negative_default`.

## Step 4 — TRIVIAL: named argument

**File:** `demetra/services/persistence/database.py:152` — `get_connection(db_name)` → `get_connection(db_name=db_name)`.

## Step 5 — MINOR: wiki doc fix

**File:** `wiki/pages/2026-08-09-apply-code-review-findings.md:110` — doc said `-- "wiki/"` and "skipped destination"; impl scopes `-- "wiki/" "AGENTS.md"` and *consumes* the second NUL record (destination first, source second for `-z` renames).

## Test Results

- New: `test_auth.py` (stale-version rejection), `test_utils.py` (negative default).
- Full: **739 passed in 4.95s**; `ruff`, `ty`, `bandit`, `tsc` + `vite build` clean.
- `alembic check` drift is pre-existing, unrelated.

---

## Follow-ups

Working tree uncommitted on `code-review`; orchestrator handles commit/PR.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-09-apply-code-review-findings]], [[2026-07-24-plain-auth-review-followups]]
- External: [manti-by/demetra#75](https://github.com/manti-by/demetra/pull/75)
