---
title: Add tests for existing feature-flag changes
date: 2026-07-22
type: implementation
status: resolved
session_id: ses_0774c35d8ffeUI6fTqrrD0UW8w
services: [settings, workflows]
branch: -
tickets: []
tags: [feature-flags, testing, ruff, pytest]
related: []
---

# Add tests for existing feature-flag changes

## TL;DR

Added a `FEATURES` dict to `demetra/settings.py` that gates `ruff` and `pytest` execution via two env-var-driven flags (`IS_RUFF_ENABLED`, `IS_PYTEST_ENABLED`), both defaulting to `False`. The lint workflow (`demetra/workflows/lint.py`) now checks these flags alongside `is_package_installed`. Existing tests were broken by the new defaults and were fixed; added 3 settings tests + 3 workflow tests covering all flag combinations.

---

## Overview

Two files were changed, two test files were updated:

- **`demetra/settings.py:42-45`** — New `FEATURES` module-level dict with two boolean keys read from env vars:
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

## Follow-ups

None.

## References

- Related: `<none>`
- External: `<none>`
