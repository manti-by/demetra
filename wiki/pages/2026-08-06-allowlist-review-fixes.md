---
title: Allowlist CodeRabbit Review Fixes and CI Test Fix
date: 2026-08-06
type: implementation
status: resolved
session_id: "-"
services: [main, auth, database, settings, tests]
branch: mnt-155-add-allow-list-for-registration-and-github-login
tickets: [MNT-155]
tags: [allowlist, code-review, coderabbit, security, auth, tests]
related:
- 2026-08-20-fix-allowlist-tests.md
- 2026-07-24-plain-auth-review-followups.md
- 2026-08-03-check-api-auth-and-credentials.md
- 2026-08-09-apply-code-review-findings.md
---

# Allowlist CodeRabbit Review Fixes and CI Test Fix

## TL;DR

Applied all actionable CodeRabbit findings on PR #71 (MNT-155 allowlist): de-prefixed functions, moved flag to `demetra/settings`, hardened admin bypass to immutable GitHub ID, validated seed-file entries, made seed CLI dry-run aware, and fixed two CI failures from `ck_users_has_auth` violations. Suite green at 619 passed.

---

## Overview

Allowlist branch had 3 nitpicks + 1 security finding + seed robustness comments and a red CI run. All closed.

## Step 1 — Rename underscore-prefixed functions

Per AGENTS.md rule.

- `main.py:186-250` — `_allowlist_add/remove/list/seed_existing` → `allowlist_*`, dispatcher calls updated.
- `demetra/services/auth/allowlist.py:55` — `_normalize_value` → `normalize_value`.

## Step 2 — Read flag from `demetra.settings`

Was reading `IS_ALLOWLIST_ENABLED` from env on every call alongside `settings.py:49`.

- `demetra/services/auth/allowlist.py:22-28` — now returns `ALLOWLIST_ENABLED` from `demetra.settings`; `os` import dropped.
- `tests/conftest.py:106` — `allowlist_seeded` patches `demetra.services.allowlist.ALLOWLIST_ENABLED`; `tests/test_allowlist.py` updated.

## Step 3 — Admin bypass via immutable GitHub ID

**Severity:** Security (CWE-863). Mutable `github_username` allowed a reassigned username to match stale admin row.

- `demetra/services/auth/allowlist.py:90-124` — signature `is_github_login_allowed(login, email, github_id)`; bypass via `get_user_by_github_id` / `users.github_id`.
- `demetra/services/auth.py:206` — passes `github_id=github_user.id`.
- Test: `test_admin_github_gate_rejects_reassigned_username` (`tests/test_allowlist.py`).

## Step 4 — Validate seed-file entries

`load_seed_file` returned raw JSON, `KeyError`/`TypeError` mid-loop.

- `demetra/services/auth/allowlist.py:256-298` — validates each entry: object, `entry_type` in `VALID_ENTRY_TYPES`, non-empty `value`, optional string `note`. Raises `ValueError` with index-relative message.

## Step 5 — Seed-file path respects dry-run

`allowlist_seed_existing` ignored `dry_run` for `ALLOWLIST_SEED_FILE`.

- `demetra/services/auth/allowlist.py:183-235` — extracted `seed_allowlist_rows(dry_run, rows)`; both paths delegate.
- `main.py:221-250` — both routes through `seed_allowlist_rows`, reports `(dry-run)` when set.

## Step 6 — Fix CI failures

```
sqlalchemy.exc.IntegrityError: violates check constraint "ck_users_has_auth"
```

- `tests/test_allowlist_cli.py:128,143` — `create_user(email=…)` lacked `password_hash`/`github_id` (`password_hash IS NOT NULL OR github_id IS NOT NULL`). Fixed with `password_hash="test-hash"`.

## Test Results

- `pytest` — **619 passed** (was 2 failed).
- `ruff`, `ruff format --check`, `ty`, bandit, `pre-commit` — clean.

---

## Consistency note (2026-08-23)

MNT-173 (PR #86) superseded Step 2 naming: gate now reads `IS_ALLOWLIST_ENABLED` default **on** (fail-closed); module moved to `demetra/services/auth/allowlist.py`. See [[2026-08-20-fix-allowlist-tests]].

## Follow-ups

- Committed `d1df1d2` and pushed to PR #71.
- `_dispose_engines` teardown "Event loop is closed" noise is harmless, could be cleaned later.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-07-24-plain-auth-review-followups]], [[2026-08-03-check-api-auth-and-credentials]], [[2026-08-09-apply-code-review-findings]], [[2026-08-20-fix-allowlist-tests]]
- External: PR #71 https://github.com/manti-by/demetra/pull/71
