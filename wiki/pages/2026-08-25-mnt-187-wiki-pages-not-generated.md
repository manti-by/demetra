---
title: Wiki pages not generated — move wiki step before commit
date: 2026-08-25
type: implementation
status: resolved
session_id: "-"
services: [main, workflows, wiki, cleanup]
branch: mnt-187-wiki-pages-not-generated
tickets: [MNT-187]
tags: [wiki, commit, push, workflow, error-handling, awaiting-input, git]
related: [2026-08-05-pr-creation-failure-handler.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md, 2026-08-07-split-wiki-service-into-subpackage.md]
---

# Wiki pages not generated — move wiki step before commit

## TL;DR

The session wiki page was written in `main.py`'s `finally` block — *after* `commit_and_push` had already committed and pushed, so the freshly-written `wiki/pages/*.md` never reached the repo. Moved the wiki write into `commit_and_push` (after the first `git add`, before the commit) targeting the worktree's own `wiki/` directory, made `git_diff_facts` diff the working tree so it sees uncommitted build changes, and converted the silently-swallowed wiki failure into a typed `WikiError` that moves the ticket to `Awaiting Input` with a `wiki_failed` comment. 5 new tests; full suite 899 passed.

---

## Overview

Every completed run ended with the wiki page being written to the *main* project's `wiki/` directory (`WIKI_ROOT = BASE_PATH / "wiki"`) at the very end of the workflow, after the commit. The page never landed in the repo:

- The wiki write happened in `main.py`'s `finally`, gated on `is_success`, so it ran after `git commit`/`git push`.
- It targeted `service.PAGES_ROOT` (the main checkout), not the worktree where the commit happens — a separate working tree of the same repo, so the new file was invisible to the branch's `git add`.
- `git_diff_facts` used `git diff <base_ref>..HEAD` (commit-to-commit), which is empty at that point anyway.

## Step 1 — Typed `WikiError` and a `wiki` session step

**File:** `demetra/library/exceptions.py` — added `class WikiError(DemetraError)` so the workflow can route wiki failures like the other typed failures (`PullRequestError`, `ReviewError`, `BuildError`).

**File:** `demetra/library/models.py` — added `"wiki"` to the `StepType` literal so `update_session_step(..., step="wiki")` is type-safe.

## Step 2 — Working-tree diff for the wiki page

**File:** `demetra/services/wiki/facts.py` — `git_diff_facts` now builds `git diff {base_ref}` (working tree vs base) instead of `git diff {base_ref}..HEAD`. The wiki is generated *before* the commit, so the build agent's uncommitted changes are exactly what the page should document. Safe for the merge/rebase flows: after a successful merge the worktree is clean, so working-tree diff and `HEAD` diff are equivalent.

## Step 3 — Configurable wiki root

The write helpers now take an optional target path so the main flow can write into the worktree while merge/rebase keep the legacy default:

- **`demetra/services/wiki/parsing.py`** — `existing_page_for_ticket(ticket_identifier, pages_root=None)`.
- **`demetra/services/wiki/index.py`** — `read_index` / `write_index` / `patch_index` / `regenerate_by_topic` accept `index_path=None`.
- **`demetra/services/wiki/render.py`** — `write_session_wiki_page(context, wiki_root=None)`; when omitted it uses the service `PAGES_ROOT`/`INDEX_PATH` (legacy), when given it writes to `<wiki_root>/pages/` and patches `<wiki_root>/INDEX.md`. Failures now `raise WikiError(f"Failed to write wiki page for {identifier}: {e}")` instead of being logged and swallowed. `WikiError` is re-exported through the `demetra.services.wiki` facade.

## Step 4 — Wiki write inside `commit_and_push`

**File:** `demetra/workflows/cleanup.py` — `commit_and_push` now:

1. `git add` the build changes (existing) and bail with `return False` when empty (existing retry loop).
2. `update_session_step(..., step="wiki")` then `write_session_wiki_page(context=context, wiki_root=context.worktree_path / "wiki")`. On success, a second `git add` stages the freshly-written `wiki/pages/*.md` + `wiki/INDEX.md` so they are part of the same commit. On failure, the error is captured in `wiki_error` and the function logs a warning but **continues** — commit/push/PR proceed without the wiki page.
3. Proceeds with `git commit` / `git push` / PR creation, marks the session step `"completed"`, then re-raises `wiki_error` if set so `main.py`'s `except WikiError` handler moves the ticket to `Awaiting Input` with a `wiki_failed` comment. Net effect: wiki generation is best-effort and never blocks shipping the code change.

> **Consistency note (2026-08-27, Consistency Agent):** Step 2 originally described an immediate `WikiError` abort before commit; follow-up commit `c2a31ab` (PR #103) changed this to deferred failure — branch/push/PR succeed first, ticket status is gated afterward. See `demetra/templates/wiki_failed.md` and `process_wiki_failure` (`demetra/workflows/failure.py:85`).

## Step 5 — Failure handling

**File:** `demetra/templates/wiki_failed.md` — new template: `## Wiki page generation failed`, the error block, and a request to move the ticket back to `In Progress`.

**File:** `demetra/workflows/failure.py` — `process_wiki_failure(context, error)` renders the template and calls the existing `notify_linear_failure(..., comment_label="wiki-failure")` (posts the comment + moves the ticket to `Awaiting Input`).

**File:** `main.py` — the wiki write was removed from the `finally` block (it is now inside `commit_and_push`), and a new `except WikiError as e:` arm (before the generic `except DemetraError`) calls `process_wiki_failure` and records `failure_step="awaiting_input"`, `should_update_linear_status=False` — mirroring the `PullRequestError`/`ReviewError` pattern from [[2026-08-05-pr-creation-failure-handler]].

## Test Results

- `tests/test_wiki.py` — `test_failure_is_swallowed` → `test_failure_raises_wiki_error` (asserts `WikiError`); new `test_writes_to_custom_wiki_root` (page + index land under `<wiki_root>`); `git_diff_facts` tests updated to assert `diff <base_ref>` without `..HEAD`.
- `tests/test_workflows.py` — `mock_commit_deps` extended with a patched `write_session_wiki_page`; every `commit_and_push` test asserts the wiki write with `wiki_root=context.worktree_path / "wiki"` and the second `git_add_all`; new `test_commit_and_push_wiki_failure_raises_wiki_error`.
- `tests/test_entrypoints.py` — new `test_main_writes_wiki_before_commit` (success path) and `test_main_handles_wiki_failure` (WikiError → `process_wiki_failure` + `awaiting_input` cleanup).
- `tests/test_failure.py` — new `test_posts_wiki_failure_comment`.

```text
899 passed in 23.56s
ruff check .  — clean
ty check      — clean
bandit        — 0 issues
pre-commit    — all hooks passed
```

---

## Follow-ups

- The merge/rebase workflows still write the wiki with the legacy default root (`WIKI_ROOT`) after their merge commit; they were left unchanged because their working tree is clean post-merge and the PR already carries the wiki page. A future pass could point them at the worktree root for consistency.
- `git_diff_facts` now captures any uncommitted changes in the worktree; the wiki page lists the wiki files themselves once staged — this is benign because the diff is computed before the page is written.

## References

- Related: [[2026-08-05-pr-creation-failure-handler]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]], [[2026-08-07-split-wiki-service-into-subpackage]]
- External: [MNT-187](https://linear.app/mnt/issue/MNT-187/wiki-pages-not-generated)