---
title: 'MNT-322: Run CI after merge'
generated: {by: demetra, at: '2026-11-26T00:00:00Z'}
description: Implemented a configurable CI loop for merge/rebase workflows that automatically fixes and retries lint/test failures up to 5 times, maintaining build status while committing fixes, with full test coverage meeting MNT-322 requirements.
type: implementation
status: stable
session_id: ses_de9460bb1ffexYKu9pkqDp361A
services: [.env.docker, settings, workflows, pyproject, test_merge_workflow, test_rebase_workflow, test_settings, test_workflows, uv, INDEX, 2026-11-26-mnt-322-run-ci-after-merge]
branch: mnt-322-run-ci-after-merge
tickets: [MNT-322]
tags: [wiki, feature, backend]
related: [2026-11-10-mnt-308-lint-error-extraction.md, 2026-10-06-unify-subprocess-env-on-session-environment.md, 2026-11-10-durable-review-attempts-budget.md]
---

# MNT-322: Run CI after merge

## TL;DR

Implemented a CI loop for merge/rebase workflows that runs linting and tests after successful merges, with up to 5 retry attempts. The system now automatically fixes CI failures by committing changes and pushing them back to the branch, while maintaining the ticket status as "build" during the process. All tests pass and the implementation meets the acceptance criteria.

## Overview

The changes introduce:
1. A configurable CI attempt budget in settings
2. A shared CI helper that runs the lint/test loop
3. Integration with merge and rebase workflows
4. Comprehensive test coverage

## Step 1 — Add CI Budget to Settings

**File:** demetra/settings.py:58
```python
MAX_ATTEMPTS: dict = {
    "ci": env_get_int("MAX_CI_ATTEMPTS", 5),
}
```

Added a new `ci` key to `MAX_ATTEMPTS` with a default of 5 attempts, configurable via environment variable.

## Step 2 — Create Shared CI Helper

**File:** demetra/workflows/lint.py:118-123
```python
async def run_ci_loop(
    target_path: Path,
    *,
    task_id: str,
    project_id: str,
    branch_name: str,
    task_title: str,
    session_id: str | None = None,
    environment: SessionEnvironment | None = None,
) -> bool:
```

The core `run_ci_loop` function:
- Sets status to "build" immediately
- Runs up to `MAX_ATTEMPTS["ci"]` repair rounds
- Commits and pushes fixes automatically
- Returns True if CI passes, False if budget is exhausted

## Step 3 — Update Merge and Rebase Workflows

**File:** demetra/workflows/merge.py
```python
from demetra.workflows.lint import run_ci_loop
```

Both merge and rebase workflows now import and use the shared `run_ci_loop` after their core operations complete.

## Test Results

All 1709 tests pass, including new tests for:
- Clean runs that skip the agent
- Failure repair and recheck cycles
- Budget exhaustion behavior
- Edge cases with empty output
- Git operations during CI fixes

**File:** tests/test_workflows.py
```python
class TestRunCiLoop:
    test_clean_run_commits_formatted_changes_and_skips_agent
    test_failure_is_repaired_committed_and_rechecked
    test_persistent_failure_exhausts_budget
    test_last_repair_is_rechecked_before_exhaustion
    test_failure_without_output_is_repaired_with_generic_prompt
```

## Follow-ups

- None

## References
- External: https://linear.app/mnt/issue/MNT-322/run-ci-after-merge
- Related: [2026-11-10-mnt-308-lint-error-extraction](/pages/2026-11-10-mnt-308-lint-error-extraction.md)
- Related: [2026-10-06-unify-subprocess-env-on-session-environment](/pages/2026-10-06-unify-subprocess-env-on-session-environment.md)
- Related: [2026-11-10-durable-review-attempts-budget](/pages/2026-11-10-durable-review-attempts-budget.md)
