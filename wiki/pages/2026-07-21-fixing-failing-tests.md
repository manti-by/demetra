---
title: Fixing Failing Tests
date: 2026-07-21
type: code-review
status: resolved
session_id: ses_07acf7185ffe4DbD6RwJDT5EBU
services: [main, test]
branch: main
tags: [testing]
related: []
---

# Fixing Failing Tests

## TL;DR

Two tests in `tests/test_project.py` were failing because `bump_project_version()` no longer raises `ValueError` — it now logs a warning and returns `None`. Updated both tests to assert `result is None` instead.

---

## Problem

Two tests in `tests/test_project.py` were failing because they expected `bump_project_version()` to raise `ValueError`, but the source code (`demetra/services/project.py`) had been changed to log a warning and return `None` instead.

## Fix

Updated both tests to match the current behavior:
- `test_missing_version_field_raises` → `test_missing_version_field_returns_none` — asserts `result is None` instead of expecting `ValueError`
- `test_invalid_version_format_raises` → `test_invalid_version_field_returns_none` — asserts `result is None` instead of expecting `ValueError`

## Test Results

500 tests passed, `ruff check` and `ty check` clean.

## Follow-ups

- None

## References

- Related: None
- External: None
