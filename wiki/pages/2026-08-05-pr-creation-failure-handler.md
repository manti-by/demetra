---
title: PR creation failure moves ticket to Awaiting Input
date: 2026-08-05
type: implementation
status: resolved
session_id: '-'
services:
- main
- workflows
- linear
- github
branch: '-'
tickets:
- MNT-23
- MNT-31
tags:
- pr
- pull-request
- error-handling
- awaiting-input
- linear
- status
- workflow
- github
- gh
related:
- 2026-02-16-update-ticket-status.md
- 2026-02-21-create-github-pr.md
- 2026-07-16-fix-empty-build-plan-loop.md
- 2026-07-21-awaiting-input-status-for-session.md
- 2026-08-19-split-auth-linear-services-and-review-failure-handling.md
---
# PR creation failure moves ticket to Awaiting Input

## TL;DR

`gh pr create` failures after a successful push previously reverted the ticket to TODO with no Linear trace. A dedicated `except PullRequestError` handler in `main.py` now posts a comment (branch, compare URL, error), moves the ticket to `Awaiting Input`, and records step `awaiting_input`.

---

## Overview

`PullRequestError` from `commit_and_push` (`demetra/workflows/cleanup.py:67`) fell through to generic `except DemetraError` → `failure_step="failed"` → `linear_cleanup(is_success=False)` moved ticket to TODO, leaving the pushed branch dangling.

## Step 1 — Dedicated handler in `main.py`

**File:** `main.py:121` — `except PullRequestError` before generic `DemetraError`:

```python
except PullRequestError as e:
    failure_step = "awaiting_input"
    should_update_linear_status = False
    body = ("## PR creation failed\n\n..."
            f"**Branch:** `{context.branch_name}`\n"
            f"**Open manually:** https://github.com/{context.project.repository_owner}/"
            f"{context.project.repository_name}/compare/{context.branch_name}\n\n"
            f"```\n{e}\n```\n")
    if not await post_comment(task_id=context.linear_task.id, body=body):
        print_message("Failed to post PR-creation-failure comment to Linear", style="error")
    await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["awaiting_input"])
```

- `failure_step="awaiting_input"` → `cleanup.py:117` records session correctly.
- `should_update_linear_status=False` prevents `cleanup.py:135` reverting to TODO.
- `str(e)` already carries `gh` stderr/stdout; comment adds compare URL.
- Worktree still cleaned via `git_cleanup` in `finally` (branch lives on remote).

## Step 2 — Tests

**File:** `tests/test_entrypoints.py` — extended `mock_main_deps` with `post_comment`/`update_ticket_status`; `test_main_handles_pr_creation_failure` asserts comment contains branch/compare URL/error, status updated to `awaiting_input`, and `cleanup_workflow` receives `should_update_linear_status=False` + `failure_step="awaiting_input"`.

## Test Results

`tests/test_entrypoints.py` + `tests/test_workflows.py` pass; full suite `587 passed`. `ruff`, `ty`, `pre-commit` clean.

---

## Source — [[2026-02-16-update-ticket-status]]

MNT-23 (2026-02-16): `update_ticket_status` / `get_ticket_states` via GraphQL; `main.py` moves to `In Progress` before plan and `In Review` after push. Failures surfaced not raised.

## Source — [[2026-02-21-create-github-pr]]

MNT-31 (2026-02-21): `create_pull_request` via `gh` CLI (`demetra/services/github.py`) returns `(exit_code, stdout, stderr)`; `GH_PATH` configurable. PR URL printed, then `In Review` update.

## Follow-ups

None.

## Consistency note (2026-08-19)

Handler extracted to `demetra/workflows/failure.py:process_pr_failure()`. Comment bodies now via `get_template()` (`pr_creation_failed`/`review_failed`); state lookup via `get_linear_config_value(name="awaiting_input")`. `ReviewError` follows identical path — see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]].

## References

- Related: [[2026-02-16-update-ticket-status]], [[2026-02-21-create-github-pr]], [[2026-07-16-fix-empty-build-plan-loop]], [[2026-07-21-awaiting-input-status-for-session]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]
