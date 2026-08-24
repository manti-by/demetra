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
related: [2026-07-24-plain-auth-review-followups.md, 2026-08-03-check-api-auth-and-credentials.md, 2026-08-09-apply-code-review-findings.md, 2026-08-20-fix-allowlist-tests.md]
---

# Allowlist CodeRabbit Review Fixes and CI Test Fix

## TL;DR

Applied every actionable CodeRabbit finding on PR #71 (MNT-155, registration/GitHub-login
allowlist): renamed underscore-prefixed functions, moved the allowlist flag into
`demetra/settings`, hardened the admin bypass to key off the immutable GitHub account id
instead of the mutable username, validated seed-file entries before insertion, and made the
seed-file CLI path dry-run aware. Also fixed the two failing CI tests whose `create_user`
calls violated the `ck_users_has_auth` check constraint. Full suite green (619 passed).

---

## Overview

The allowlist feature branch had an open CodeRabbit review (3 nitpicks + 1 security finding
+ seed-file robustness inline comments) and a red CI run. This session closed them all.

## Step 1 — Rename underscore-prefixed functions

Per the AGENTS.md rule "never prefix functions with `_`".

**File:** `main.py:186-250` — `_allowlist_add` / `_allowlist_remove` / `_allowlist_list` /
`_allowlist_seed_existing` → `allowlist_add` / `allowlist_remove` / `allowlist_list` /
`allowlist_seed_existing`, and the four dispatcher calls updated.

**File:** `demetra/services/auth/allowlist.py:55` — `_normalize_value` → `normalize_value`,
call sites updated (add_entry, remove_entry, seed loop).

## Step 2 — Read the flag from `demetra.settings`

`is_allowlist_enabled()` previously read `IS_ALLOWLIST_ENABLED` from the process environment
on every call, creating a second config path alongside `settings.py:49`.

**File:** `demetra/services/auth/allowlist.py:22-28` — now returns the `ALLOWLIST_ENABLED`
constant imported from `demetra.settings`; the `os` import was dropped.

**File:** `tests/conftest.py:106` — `allowlist_seeded` now patches
`demetra.services.allowlist.ALLOWLIST_ENABLED` instead of `monkeypatch.setenv`, and the
env-based tests in `tests/test_allowlist.py` follow suit.

## Step 3 — Bind the admin bypass to the immutable GitHub id

**Severity:** Security (CWE-863). `is_github_login_allowed` authorized admins by the mutable
`users.github_username`; if a former admin username is reassigned to another GitHub account,
that account could match the stale admin row before any JWT was issued.

**File:** `demetra/services/auth/allowlist.py:90-124` — signature is now
`is_github_login_allowed(login, email, github_id)`; the admin bypass queries
`get_user_by_github_id` (via `users.github_id`). `github_username` allowlist/email OR-match is
unchanged.

**File:** `demetra/services/auth.py:206` — `authenticate_user` passes `github_id=github_user.id`.

**Test:** added `test_admin_github_gate_rejects_reassigned_username`
(`tests/test_allowlist.py`): a non-admin account reusing the admin's old username is rejected.

## Step 4 — Validate seed-file entries before insertion

`load_seed_file` returned raw JSON and let `KeyError`/`TypeError` surface mid-loop.

**File:** `demetra/services/auth/allowlist.py:256-298` — every entry is now validated before any
insert: must be an object, `entry_type` in `VALID_ENTRY_TYPES`, `value` a non-empty string,
`note` optional and a string. Invalid entries raise `ValueError` with an actionable index-relative
message that the existing CLI error handler prints.

## Step 5 — Make the seed-file path dry-run aware

`allowlist_seed_existing` (main.py) ignored its `dry_run` argument when seeding from
`ALLOWLIST_SEED_FILE` and inserted unconditionally.

**File:** `demetra/services/auth/allowlist.py:183-235` — extracted the row-processing loop into
`seed_allowlist_rows(dry_run, rows)`; `seed_existing_users` now delegates to it, and the CLI
file path calls it too, so dry-run reports counts without writing.

**File:** `main.py:221-250` — `allowlist_seed_existing` routes both paths through
`seed_allowlist_rows` and prints the same inserted/already-present/skipped report with the
`(dry-run)` prefix.

## Step 6 — Fix the failing CI tests

CI "Run checks" failed with:

```text
sqlalchemy.exc.IntegrityError: new row for relation "users" violates check constraint
"ck_users_has_auth"
```

**File:** `tests/test_allowlist_cli.py:128,143` — `test_seed_existing_dry_run_reports_counts`
and `test_seed_existing_inserts_and_is_idempotent` called `create_user(email=email)` with
neither a password nor a GitHub id, violating the `password_hash IS NOT NULL OR github_id
IS NOT NULL` constraint. Fixed by passing `password_hash="test-hash"`.

## Test Results

- `uv run pytest tests/` — **619 passed** (was `2 failed, 616 passed` on CI).
- `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, bandit — clean.
- `uv run pre-commit run --files ...` — all hooks pass.

---

## Consistency note (2026-08-23)

MNT-173 (PR #86, 2026-08-20) superseded Step 2's naming: the gate now reads
`IS_ALLOWLIST_ENABLED` from `demetra.settings` with default **on** (fail-closed), and the
module moved to `demetra/services/auth/allowlist.py` during the auth subpackage split —
the `is_allowlist_enabled()` helper and the flat `demetra/services/allowlist.py` module no
longer exist. The file paths below keep their historical line numbers; see
[[2026-08-20-fix-allowlist-tests]] for the follow-up default-on refactor and test fixes.

## Follow-ups

- ~~Changes are staged but not yet committed/pushed, so CI has not re-run with the fixes.~~
  **Done** — committed as `d1df1d2` ("MNT-155: Fix tests and update wiki") and pushed to
  PR #71 (branch `mnt-155-add-allow-list-for-registration-and-github-login`).
- The `_dispose_engines` teardown in `tests/test_allowlist_cli.py` logs noisy
  "Event loop is closed" errors; harmless (tests still pass) but could be cleaned up later.

## References

- Related: [[2026-07-24-plain-auth-review-followups]] (password auth + review follow-ups),
  [[2026-08-03-check-api-auth-and-credentials]] (auth API hardening),
  [[2026-08-09-apply-code-review-findings]] (subsequent review findings applied),
  [[2026-08-20-fix-allowlist-tests]] (MNT-173 default-on refactor and test fixes)
- External: PR #71 https://github.com/manti-by/demetra/pull/71
