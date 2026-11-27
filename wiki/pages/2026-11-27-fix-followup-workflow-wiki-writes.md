---
title: Fix uncommitted wiki writes in merge, rebase and review-fixes workflows
generated: {by: demetra, at: '2026-11-27T15:50:00Z'}
description: Stops merge and rebase workflows from writing uncommitted wiki files and revalidation runs into BASE_PATH, and moves review-fixes wiki generation into the PR worktree before commit and push so auto-deploys are no longer blocked.
type: implementation
status: stable
session_id: sess_6b76ec20-b97f-4c01-895f-d3c162bdf7e8
services: [workflows/merge, workflows/rebase, workflows/review_fixes, test_merge_workflow, test_rebase_workflow, test_review_fixes_workflow]
branch: master
tickets: []
tags: [wiki, deploy, workflows, merge, rebase, review-fixes, bug]
related: [2026-08-25-mnt-187-wiki-pages-not-generated.md, 2026-09-02-review-findings-cleanup.md, 2026-11-14-mnt-315-auto-deploy-on-master-commits.md, 2026-11-25-mnt-323-worker-generation-swap.md, 2026-11-25-deploy-deadlock-container-cleanup.md]
---

# Fix uncommitted wiki writes in merge, rebase and review-fixes workflows

## TL;DR

Automatic deploys on merge to `master` were finding dirty `wiki/pages/*.md` and `wiki/INDEX.md` files in the host checkout because `merge`, `rebase`, and `review_fixes` still ran `write_session_wiki_page(context=context)` without `wiki_root` in their `finally:` blocks after pushing — writing straight into `BASE_PATH / "wiki"` (`.:/srv/demetra/src/` in the worker containers). Wiki writes and `BASE_PATH` revalidation enqueues were removed from `merge` and `rebase`, while `review_fixes` now writes to `worktree_path / "wiki"` and stages the files into the fix commit before `git_commit` and `git_force_push` (committed as `7bc1327`).

## Overview

When [2026-08-25-mnt-187-wiki-pages-not-generated](/pages/2026-08-25-mnt-187-wiki-pages-not-generated.md) moved wiki generation into `commit_and_push` (`demetra/workflows/cleanup.py:98`) with `wiki_root=context.worktree_path / "wiki"`, the PR follow-up workflows (`merge.py`, `rebase.py`, and later `review_fixes.py`) kept calling `write_session_wiki_page(context=context)` in `finally:` with `wiki_root=None`.

In the Docker Compose stack (`docker-compose.yaml:23`), `worker-blue` and `worker-green` bind-mount the host deploy checkout (`.`) at `/srv/demetra/src/` (`BASE_PATH`). Omitting `wiki_root` caused every `@demetra-ai merge`, `@demetra-ai rebase`, and `@demetra-ai fix review findings` run — even for external target repositories — to write an uncommitted page and rewrite `wiki/INDEX.md` directly in `DEPLOY_HOST_CHECKOUT`. When the PR merged to `master`, the auto-deploy daemon from [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md) and [2026-11-25-mnt-323-worker-generation-swap](/pages/2026-11-25-mnt-323-worker-generation-swap.md) either failed `git pull --ff-only` on conflicting working-tree files or aborted in `checkout_has_no_local_changes` (`demetra/services/daemons/deployer.py:420-446`).

## Step 1 — Remove post-push wiki writes and revalidation from merge and rebase

**File:** `demetra/workflows/merge.py` and `demetra/workflows/rebase.py`

Initial PR creation already commits the session wiki page on the PR branch, and `perform_git_merge` / `perform_git_rebase` reconcile that branch with `origin/master`. Both workflows dropped their `finally:` `write_session_wiki_page` blocks (and `merge.py` dropped the `WIKI["revalidation_enabled"]` `run_wiki_revalidation` enqueue, which also mutated `BASE_PATH / "wiki"` without pushing), leaving only worktree removal and `update_session_step`:

```python
    finally:
        if worktree_path and project is not None:
            try:
                await git_worktree_remove(
                    target_path=project.local_path,
                    worktree_path=worktree_path,
                    environment=environment,
                    force=True,
                    project_id=project.id,
                )
            except (OSError, RuntimeError):
                logger.warning(msg=f"Failed to clean up worktree at {worktree_path}")
        await update_session_step(task_id=task_id, step=final_step)
```

## Step 2 — Write and commit review-fixes wiki updates inside the PR worktree

**File:** `demetra/workflows/review_fixes.py:120-161, 293-315`

`_record_review_fixes_wiki` now targets `wiki_root=worktree_path / "wiki"`, drops the `run_wiki_revalidation` enqueue, and returns a boolean indicating whether the wiki write succeeded:

```python
        context = Context(
            project=project,
            auto_mode=True,
            task=task,
            branch_name=head_branch,
            worktree_path=worktree_path,
            session=session,
        )
        await write_session_wiki_page(context=context, wiki_root=worktree_path / "wiki")
        return True
```

In `run_review_fixes_workflow`, `_record_review_fixes_wiki` runs after verifying the agent produced changes (so no-op runs skip wiki generation) and before `git_commit` / `git_force_push`. A second `git_add_all` stages the wiki files only when `_record_review_fixes_wiki` returns `True`, preserving best-effort behavior when wiki generation fails:

```python
        if await _record_review_fixes_wiki(
            task_id=task_id,
            project=project,
            session=session,
            head_branch=head_branch,
            worktree_path=worktree_path,
        ):
            has_staged = await git_add_all(target_path=worktree_path, environment=environment, project_id=project.id)

        if has_staged:
            await git_commit(
                target_path=worktree_path,
                message=f"fix: address review findings for PR #{pr_number}",
                environment=environment,
                project_id=project.id,
            )

        await git_force_push(
            target_path=worktree_path, branch_name=head_branch, environment=environment, project_id=project.id
        )
```

## Test Results

- Updated `tests/test_merge_workflow.py` and `tests/test_rebase_workflow.py` to remove the legacy wiki mocks and assert `PAGES_ROOT` and `INDEX_PATH` remain untouched.
- Added `tests/test_review_fixes_workflow.py` (`TestRunReviewFixesWorkflow`) covering worktree wiki writes (`add -> wiki -> add -> commit -> push -> remove`), agent-committed changes, best-effort fallback on `WikiError`, and skipping wiki writes when no changes were made.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check`, `uv run python -m bandit -c pyproject.toml -q -r demetra/`, and `uv run python -m pytest` on the workflow and wiki suites (`239 passed`) all passed cleanly.

## Follow-ups

- Run a one-time `git checkout -- wiki/ && git clean -fd wiki/` in the production host checkout (`/home/manti/www/demetra`) after deploying so leftover dirty wiki files from prior runs do not block `deployer` (see [2026-11-25-deploy-deadlock-container-cleanup](/pages/2026-11-25-deploy-deadlock-container-cleanup.md)).
- Consider retiring the unused `run_wiki_revalidation` / `WIKI_REVALIDATION_ENABLED` helpers in `demetra/services/wiki/maintenance.py` once confirmed unneeded.

## References

- Related: [2026-08-25-mnt-187-wiki-pages-not-generated](/pages/2026-08-25-mnt-187-wiki-pages-not-generated.md)
- Related: [2026-09-02-review-findings-cleanup](/pages/2026-09-02-review-findings-cleanup.md)
- Related: [2026-11-14-mnt-315-auto-deploy-on-master-commits](/pages/2026-11-14-mnt-315-auto-deploy-on-master-commits.md)
- Related: [2026-11-25-mnt-323-worker-generation-swap](/pages/2026-11-25-mnt-323-worker-generation-swap.md)
- Related: [2026-11-25-deploy-deadlock-container-cleanup](/pages/2026-11-25-deploy-deadlock-container-cleanup.md)
