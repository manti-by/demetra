---
title: PR creation failure moves ticket to Awaiting Input
date: 2026-08-05
type: implementation
status: resolved
session_id: "-"
services: [main, workflows, linear, github]
branch: "-"
tickets: [MNT-23, MNT-31]
tags: [pr, pull-request, error-handling, awaiting-input, linear, status, workflow, github, gh]
related: [2026-07-21-awaiting-input-status-for-session.md, 2026-02-16-update-ticket-status.md, 2026-02-21-create-github-pr.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md, 2026-07-16-fix-empty-build-plan-loop.md]
---

# PR creation failure moves ticket to Awaiting Input

## TL;DR

When `gh pr create` fails at the end of the workflow (after the branch was already pushed), the ticket used to be silently moved back to TODO with no trace on the Linear side. A dedicated `except PullRequestError` handler in `main.py` now posts a Linear comment with the branch, a manual compare URL and the `gh` error, then moves the ticket to `Awaiting Input` and records the session step as `awaiting_input`. Tests added.

---

## Overview

Before this change a `PullRequestError` raised in `commit_and_push` (`demetra/workflows/cleanup.py:67`) fell through to the generic `except DemetraError` in `main.py`, which set `is_success=False` and `failure_step="failed"`. `cleanup_workflow` then called `linear_cleanup(... is_success=False)`, moving the ticket back to TODO — no comment, no explanation, and the pushed branch left dangling with no PR.

## Step 1 — Dedicated handler in `main.py`

**File:** `main.py:121`

Added an `except PullRequestError` clause before the generic `DemetraError` handler:

```python
except PullRequestError as e:
    print_message(f"Pull request creation failed: {e}", style="error")
    failure_step = "awaiting_input"
    should_update_linear_status = False
    body = (
        "## PR creation failed\n\n"
        "The build, commit, and push steps succeeded, but creating the "
        "GitHub pull request failed. The branch has been pushed; the PR has "
        "not been created.\n\n"
        f"**Branch:** `{context.branch_name}`\n"
        f"**Open manually:** "
        f"https://github.com/{context.project.repository_owner}/"
        f"{context.project.repository_name}/compare/{context.branch_name}\n\n"
        "### Error\n\n"
        f"```\n{e}\n```\n\n"
        "Please create the PR manually, then move the ticket back to "
        "`In Progress` to continue."
    )
    if not await post_comment(task_id=context.linear_task.id, body=body):
        print_message("Failed to post PR-creation-failure comment to Linear", style="error")
    await update_ticket_status(task_id=context.linear_task.id, state_id=LINEAR["states"]["awaiting_input"])
```

Key mechanics:
- `failure_step="awaiting_input"` makes `cleanup_workflow` record the session step as `awaiting_input` (`cleanup.py:117`), matching the `AutoCancelledError` path.
- `should_update_linear_status=False` stops `linear_cleanup` from reverting the ticket to TODO (`cleanup.py:135-136`).
- The `PullRequestError` message already carries `stderr or stdout` from `gh pr create`, so `str(e)` is the actionable error. The comment adds the branch and a `compare/<branch>` URL for a manual PR.
- The worktree is still cleaned up by `git_cleanup` in the `finally` — correct, because the branch lives on the remote.

## Step 2 — Tests

**File:** `tests/test_entrypoints.py`

Extended the `mock_main_deps` fixture to also expose `post_comment` / `update_ticket_status` mocks, and added `test_main_handles_pr_creation_failure`: `commit_and_push` raises `PullRequestError("gh: could not create PR")`, then asserts the comment body contains the branch, the compare URL and the error text, that `update_ticket_status` is called with the `awaiting_input` state, and that `cleanup_workflow` receives `should_update_linear_status=False` with `failure_step="awaiting_input"`.

## Test Results

`tests/test_entrypoints.py` (full file) and `tests/test_workflows.py` pass; full suite `587 passed`. `ruff`, `ty` and `pre-commit` (incl. bandit) all pass.

---

## Source — [[2026-02-16-update-ticket-status]]

Originally added in [[2026-02-16-update-ticket-status]] on 2026-02-16 (MNT-23): the
Linear service exposes `update_ticket_status(ticket_id, state)` (GraphQL mutation) and
`get_ticket_states(...)` (valid state names for the team). `main.py` moves the ticket to
`In Progress` before the plan agent runs and to `In Review` after pushing to GitHub.
Status updates are wrapped so a Linear API failure does not abort the workflow — the
failure is surfaced, not raised (the current error handling raises `LinearError` for
malformed payloads; see [[2026-07-16-fix-empty-build-plan-loop]]).

## Source — [[2026-02-21-create-github-pr]]

Originally added in [[2026-02-21-create-github-pr]] on 2026-02-21 (MNT-31): after
`git push`, the workflow creates the GitHub PR itself via the `gh` CLI — the
`create_pull_request(branch_name)` service in `demetra/services/github.py` returns
`(exit_code, stdout, stderr)`. The PR URL is printed and the run continues (including
the `In Review` ticket update from MNT-23). The `gh` CLI path is configurable via the
`GH_PATH` setting (default `/usr/bin/gh`).

## Follow-ups

None.

## Consistency note (2026-08-19)

- The inline handler shown above was extracted to `demetra/workflows/failure.py:process_pr_failure()`. Comment bodies are now generated from prompt templates (`pr_creation_failed`, `review_failed`) via `get_template()`, and the Linear state lookup goes through `get_linear_config_value(name="awaiting_input")` instead of directly referencing `LINEAR["states"]["awaiting_input"]`.
- `ReviewError` (LLM failure during review summarization) now follows the identical failure path — same `process_pr_failure`, same `failure_step="awaiting_input"` and `should_update_linear_status=False` — see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]].

## References

- Related: [[2026-07-21-awaiting-input-status-for-session]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]] (review-failure handling extracted into the same PR)
