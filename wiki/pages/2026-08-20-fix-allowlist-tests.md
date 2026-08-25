---
title: Fix allowlist tests after MNT-173 default-on refactor
date: 2026-08-20
type: implementation
status: resolved
session_id: ses_fe1248211ffeLvd40e4OnV1uVR
services: [auth, settings, tests]
branch: "-"
tickets: [MNT-173]
tags: [allowlist, auth, settings, tests, feature-flag]
related: [2026-08-06-allowlist-review-fixes.md, 2026-08-18-test-db-isolation-logging.md]
---

# Fix allowlist tests after MNT-173 default-on refactor

## TL;DR

The staged MNT-173 refactor ("Allowlist does not work") replaced the allowlist gate's `is_allowlist_enabled()` / `ALLOWLIST_ENABLED` (default **off**) with a settings constant `IS_ALLOWLIST_ENABLED = env_get_bool(..., True)` (default **on**, fail-closed). This left the test suite half-adapted, producing 12 failures + 23 errors. Fixed `tests/conftest.py` and the affected auth tests to match the new API and default; the full suite is green again (**883 passed**) with ruff / ty / bandit clean.

## Overview

The gate previously defaulted to off (`parse_allowlist_flag(None) → False`), which is exactly why the allowlist "did not work" — it never enforced anything. The MNT-173 fix flips the default to on and reads the flag straight from `demetra.settings` as `IS_ALLOWLIST_ENABLED`. The source changes were staged but the tests still referenced the removed API and assumed the off default.

## Step 1 — Fix the `allowlist_seeded` fixture

`tests/conftest.py` `allowlist_seeded` patched the removed module attribute `demetra.services.auth.allowlist.ALLOWLIST_ENABLED`, so every test requesting it errored with `AttributeError`. It now patches the current name in the same module namespace where the gate functions read it.

**File:** `tests/conftest.py:176` — `allowlist_seeded` now sets `demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED` → `True`. Added a companion `allowlist_disabled` fixture that sets the same attribute → `False` for tests exercising auth flows that expect no gate.

## Step 2 — Correct the monkeypatch target

`is_email_allowed` / `is_github_login_allowed` read `IS_ALLOWLIST_ENABLED` via `from demetra.settings import ... IS_ALLOWLIST_ENABLED`, which binds a **copy** into the `allowlist` module namespace. Two login tests patched `demetra.settings.IS_ALLOWLIST_ENABLED` — a no-op for the code path. They now patch `demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED`.

**File:** `tests/test_allowlist.py:111-125` — `test_login_rejects_non_allowlisted_existing_user` and `test_login_allows_allowlisted_existing_user`. These also had a second bug: `_create_password_user` (signup) ran with the gate on and an un-allowlisted email, so signup itself failed before login. Both now request `allowlist_disabled` to create the user, then flip the gate on via monkeypatch for the login assertion.

## Step 3 — Opt failing auth tests out of the on-by-default gate

With the default now on, every test that signs up / logs in / authenticates a user without an allowlist entry fails. Added `allowlist_disabled` to those tests:

**File:** `tests/test_allowlist.py` — `test_signup_allows_when_flag_off`, `test_login_allows_when_flag_off`, `test_github_allows_when_flag_off`.

**File:** `tests/test_auth.py` — `test_authenticate_user_creates_new_user`, `test_signup_creates_user_and_returns_auth_response`, `test_signup_raises_on_duplicate_email`, `test_login_returns_auth_response`, `test_login_raises_on_wrong_password`, `test_reset_password_revokes_all_tokens_and_updates_hash`, `test_reset_password_rejects_token_minted_before_reset`.

Tests that don't create/authenticate a user (invalid-email signup, unknown-email login/reset, all-mocked API endpoints) are unaffected and pass without the fixture.

## Test Results

- `uv run pytest tests/` — **883 passed**
- `uv run pre-commit run --files ...` — all hooks pass (ruff, ruff format, bandit, ...)
- `uv run ruff check`, `uv run ty check`, `uv run bandit` — clean

---

## Follow-ups

- ~~The staged MNT-173 source change (default-on `IS_ALLOWLIST_ENABLED`) is uncommitted and
  awaiting the orchestrator's commit.~~ **Done** — merged to `master` via PR #86 (`73cfea5`,
  "MNT-173: Allowlist does not work", 2026-08-20). Deploy notes / env docs should still
  reflect the default-on behavior. Verified on current master: `IS_ALLOWLIST_ENABLED =
  env_get_bool("IS_ALLOWLIST_ENABLED", True)` (`demetra/settings.py:72`).

## Consistency note (2026-08-23)

The `parse_allowlist_flag()` helper mentioned in the Overview was part of the staged
MNT-173 state; the merged form on `master` reads the flag directly via
`env_get_bool(..., True)` with no spell-tolerant parser.

## Consistency note (2026-08-24)

Frontmatter `branch: -` was unquoted YAML (parsed as a sequence); quoted to `"-"` so
frontmatter parses cleanly.

## References

- Related: [[2026-08-06-allowlist-review-fixes]], [[2026-08-18-test-db-isolation-logging]]
- External: [MNT-173 — Allowlist does not work](https://linear.app/mnt/issue/MNT-173)
