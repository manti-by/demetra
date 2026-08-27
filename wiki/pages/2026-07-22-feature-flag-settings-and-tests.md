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
related: [2026-02-20-add-pre-commit-checks-and-tests.md]
---

# Add tests for existing feature-flag changes

## TL;DR

Added a `FEATURES` dict to `demetra/settings.py` that gates `ruff` and `pytest` execution via two env-var-driven flags (`IS_RUFF_ENABLED`, `IS_PYTEST_ENABLED`), both defaulting to `False`. The lint workflow (`demetra/workflows/lint.py`) now checks these flags alongside `is_package_installed`. Existing tests were broken by the new defaults and were fixed; added 3 settings tests + 3 workflow tests covering all flag combinations.

---

## Overview

Two files were changed, two test files were updated:

- **`demetra/settings.py`** (currently lines 53-56) — New `FEATURES` module-level dict with two boolean keys read from env vars:
  ```python
  FEATURES: dict = {
      "is_ruff_enabled": os.environ.get("IS_RUFF_ENABLED", "False").lower() == "true",
      "is_pytest_enabled": os.environ.get("IS_PYTEST_ENABLED", "False").lower() == "true",
  }
  ```
  Both default to `False`, so no tooling runs unless explicitly opted in via environment.

- **`demetra/workflows/lint.py:14-17, 31-34`** — `run_lint_and_test` now requires `FEATURES["is_ruff_enabled"]` / `FEATURES["is_pytest_enabled"]` to be `True` *in addition* to the package being installed before running the respective step.

## Step 1 — Add settings tests for `FEATURES`

**File:** `tests/test_settings.py`

Three new tests following the existing `monkeypatch` + `importlib.reload` pattern:

- `test_features_defaults_disabled` — verifies both keys are `False` with no env vars set
- `test_features_env_override` — sets both `IS_RUFF_ENABLED=true` and `IS_PYTEST_ENABLED=true`, expects both `True`
- `test_features_partial_override` — enables only ruff, expects pytest still `False`

## Step 2 — Fix and extend workflow lint tests

**File:** `tests/test_workflows.py` (`TestWorkflowLint`)

Since `FEATURES` defaults to `False` in test environments, two existing tests that expected ruff/pytest to run were failing. Added an autouse fixture `mock_features_enabled` that patches `demetra.workflows.lint.FEATURES` to enable both flags for the existing tests.

Three new tests cover the gating logic:

- `test_ruff_skipped_when_feature_disabled` — `is_ruff_enabled=False`, `is_pytest_enabled=True`: only pytest runs, ruff format+checks are not called
- `test_pytest_skipped_when_feature_disabled` — `is_ruff_enabled=True`, `is_pytest_enabled=False`: ruff runs, pytest is not called
- `test_both_features_disabled_skips_everything` — neither runs, returns `(False, None)`

All three use `patch.dict("demetra.workflows.lint.FEATURES", ...)` for scoped overrides.

## Test Results

```
tests/test_workflows.py::TestWorkflowLint::test_run_lint_and_test_returns_errors PASSED
tests/test_workflows.py::TestWorkflowLint::test_run_lint_and_test_no_errors     PASSED
tests/test_workflows.py::TestWorkflowLint::test_ruff_skipped_when_feature_disabled     PASSED
tests/test_workflows.py::TestWorkflowLint::test_pytest_skipped_when_feature_disabled   PASSED
tests/test_workflows.py::TestWorkflowLint::test_both_features_disabled_skips_everything PASSED
tests/test_settings.py::TestSettings::test_features_defaults_disabled    PASSED
tests/test_settings.py::TestSettings::test_features_env_override         PASSED
tests/test_settings.py::TestSettings::test_features_partial_override     PASSED
```

All 17 tests pass (5 lint workflow + 11 existing settings + 1 existing other test).

---

## Source — [[2026-02-20-add-pre-commit-checks-and-tests]]

Originally added in [[2026-02-20-add-pre-commit-checks-and-tests]] on 2026-02-20
(MNT-21): the post-build gate is `make check` (`ty` type checking + the pre-commit
suite: Ruff lint + import management) and `make test` (pytest); failures are fed back
to the build agent for another build→check iteration. pytest is auto-detected so the
runner falls back gracefully when the suite is absent. `.coderabbit.yaml` was added
here as the project-wide CodeRabbit review config. The feature-flag gating above
(`FEATURES`) is what makes these runs opt-in today — see AGENTS.md's `is_ruff_enabled`
/ `is_pytest_enabled`.

## Follow-ups

None.

> **Status update (2026-08-27, Consistency Agent):** The `FEATURES` dict now reads via a shared
> `env_get_bool(name, default)` helper (`demetra/services/runtime/utils.py:240`) instead of the
> inline `os.environ.get(...).lower() == "true"` shown in Overview above —
> `demetra/settings.py:53-56` is now `env_get_bool("IS_RUFF_ENABLED", False)` /
> `env_get_bool("IS_PYTEST_ENABLED", False)`. Behavior (both default `False`, same env-var names)
> is unchanged; only the exact code snippet above is stale.

## References

- Related: `<none>`
- External: `<none>`
