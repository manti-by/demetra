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

MNT-173 flipped the allowlist gate from default-off (`ALLOWLIST_ENABLED`/`is_allowlist_enabled()`) to default-on `IS_ALLOWLIST_ENABLED = env_get_bool(..., True)` (fail-closed), leaving 12 failures + 23 errors from tests patching the removed API and assuming off. Fixed `tests/conftest.py` and affected auth tests to patch `demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED` and use `allowlist_disabled` where needed. Suite green again (883 passed), ruff/ty/bandit clean.

## Overview

Previous default `parse_allowlist_flag(None) → False` meant the allowlist never enforced — the bug. Staged source fix flipped default to on; tests still referenced removed names and off-default assumption.

## Changes

**`tests/conftest.py:176` — fixture** — `allowlist_seeded` now patches `demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED → True` (was `demetra.services.auth.allowlist.ALLOWLIST_ENABLED` → `AttributeError`). Added `allowlist_disabled` (`→ False`) for flows expecting no gate.

**`tests/test_allowlist.py:111-125` — monkeypatch target** — `is_email_allowed`/`is_github_login_allowed` read `IS_ALLOWLIST_ENABLED` via `from demetra.settings import ...` (copy in `allowlist` namespace), so patching `demetra.settings.IS_ALLOWLIST_ENABLED` was a no-op. Now patches `demetra.services.auth.allowlist.IS_ALLOWLIST_ENABLED`. Also fixed `_create_password_user` bug: both login tests created user via signup with gate on and un-allowlisted email → signup failed before login. Now request `allowlist_disabled` to create user, then flip gate on for login assertion. Added `allowlist_disabled` to `test_signup_allows_when_flag_off`, `test_login_allows_when_flag_off`, `test_github_allows_when_flag_off`.

**`tests/test_auth.py` — opt-out** — Added `allowlist_disabled` to `test_authenticate_user_creates_new_user`, `test_signup_creates_user_and_returns_auth_response`, `test_signup_raises_on_duplicate_email`, `test_login_returns_auth_response`, `test_login_raises_on_wrong_password`, `test_reset_password_revokes_all_tokens_and_updates_hash`, `test_reset_password_rejects_token_minted_before_reset`. Non-user-creation tests unaffected.

## Test Results

- `uv run pytest tests/` — **883 passed**
- `uv run pre-commit run --files ...` / `ruff check` / `ty check` / `bandit` — clean

## Follow-ups

- ~~Staged MNT-173 source change awaiting commit~~ **Done** — merged via PR #86 (`73cfea5`, 2026-08-20). Verified: `IS_ALLOWLIST_ENABLED = env_get_bool("IS_ALLOWLIST_ENABLED", True)` (`demetra/settings.py:72`).

## Consistency note (2026-08-23)

`parse_allowlist_flag()` was staged-state; merged form reads `env_get_bool(..., True)` with no spell-tolerant parser.

## Consistency note (2026-08-24)

Frontmatter `branch: -` quoted to `"-"` for valid YAML.

## References

- Related: [[2026-08-06-allowlist-review-fixes]], [[2026-08-18-test-db-isolation-logging]]
- External: [MNT-173 — Allowlist does not work](https://linear.app/mnt/issue/MNT-173)
