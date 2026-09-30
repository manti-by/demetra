---
name: fix-failing-tests
description: Use when asked to fix failing tests, run the test suite and repair broken assertions, or debug test failures in this project. Triggered by "fix tests", "fix failing tests", "tests are failing", "make tests pass", "test failure".
---

# Fix Failing Tests

Run this project's test suite and fix any failures systematically.

## Process

1. Run the full suite: `uv run pytest tests/ -q` (or `make test`). For a faster loop on a known area, target one file: `uv run pytest tests/test_<module>.py -q`.
2. Check recently changed files (`git diff`, `git log --stat -1`) for likely causes.
3. Prioritize updating tests to match an intentional behavior change before modifying source code — only fix source when the test correctly describes the intended behavior.
4. For each failure:
   - Read the failure output and traceback.
   - Understand what the test expects vs what the code produces.
   - Fix the source code if the test is correct.
   - Update the test if the behavior change was intentional.
   - Keep new/changed tests inside a `Test<Feature>` class per AGENTS.md (the only accepted module-level exceptions are `tests/test_allowlist_cli.py` and `tests/test_migrations.py`).
5. Rerun the affected test file after each fix to confirm resolution before moving to the next failure.
6. Run `uv run pytest tests/ -q` once more at the end to confirm the full suite is green.
7. If the change touches lint- or type-sensitive code, also run `uv run ruff check .` and `uv run ty check`.
