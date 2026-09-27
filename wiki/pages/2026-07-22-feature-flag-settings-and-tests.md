---
title: Add tests for existing feature-flag changes
date: 2026-07-22
type: implementation
status: resolved
session_id: ses_0774c35d8ffeUI6fTqrrD0UW8w
services: [settings, workflows, lint]
branch: "-"
tickets: [MNT-21]
tags: [feature-flags, testing, ruff, pytest, pre-commit, lint]
related:
- 2026-02-20-add-pre-commit-checks-and-tests.md
---

# Add tests for existing feature-flag changes

## TL;DR

Added `FEATURES` dict to `demetra/settings.py` gating `ruff`/`pytest` via `IS_RUFF_ENABLED`/`IS_PYTEST_ENABLED` (both default `False`), and made `demetra/workflows/lint.py:14-17, 31-34` check those flags alongside `is_package_installed`. Fixed broken existing tests and added 6 new ones covering all flag combinations. All 17 tests pass.

## Overview

- **`demetra/settings.py:53-56`** — `FEATURES` dict, both flags `os.environ.get(..., "False").lower() == "true"` (now via `env_get_bool` helper — see status note).
- **`demetra/workflows/lint.py:14-17, 31-34`** — `run_lint_and_test` requires `FEATURES["is_ruff_enabled"]` / `FEATURES["is_pytest_enabled"]` in addition to package installed.

## Step 1 — Settings tests

**File:** `tests/test_settings.py` — 3 tests using `monkeypatch` + `importlib.reload`:

- `test_features_defaults_disabled` — no env vars → both `False`
- `test_features_env_override` — both `true` → both `True`
- `test_features_partial_override` — only ruff enabled → pytest still `False`

## Step 2 — Workflow lint tests

**File:** `tests/test_workflows.py` (`TestWorkflowLint`)

Existing tests expected ruff/pytest to run, but `FEATURES` defaults `False` in test env — added autouse fixture `mock_features_enabled` patching `demetra.workflows.lint.FEATURES` to enable both.

3 new gating tests via `patch.dict("demetra.workflows.lint.FEATURES", ...)`:

- `test_ruff_skipped_when_feature_disabled` — `is_ruff_enabled=False` → only pytest runs
- `test_pytest_skipped_when_feature_disabled` — `is_pytest_enabled=False` → only ruff runs
- `test_both_features_disabled_skips_everything` — neither runs, returns `(False, None)`

## Test Results

All 8 feature-flag tests + 9 existing = 17 passed.

## Source — [[2026-02-20-add-pre-commit-checks-and-tests]]

Post-build gate is `make check` (ty + ruff via pre-commit) and `make test` (pytest), fed back to build agent. `FEATURES` makes these opt-in — see AGENTS.md `is_ruff_enabled`/`is_pytest_enabled`.

## Follow-ups

None.

> **Status update (2026-08-27):** `FEATURES` now reads via `env_get_bool(name, default)` (`demetra/services/runtime/utils.py:240`) instead of inline `os.environ.get(...).lower() == "true"` — `demetra/settings.py:53-56` uses `env_get_bool("IS_RUFF_ENABLED", False)` / `env_get_bool("IS_PYTEST_ENABLED", False)`, behavior unchanged.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: `<none>`
- External: `<none>`
