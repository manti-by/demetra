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
related:
- 2026-08-05-pr-creation-failure-handler.md
- 2026-08-19-split-auth-linear-services-and-review-failure-handling.md
- 2026-08-07-split-wiki-service-into-subpackage.md
---

# Wiki pages not generated — move wiki step before commit

## TL;DR

Wiki pages were written in `main.py`'s `finally` after `commit_and_push` committed/pushed, targeting the main checkout (`WIKI_ROOT = BASE_PATH / "wiki"`) not the worktree — so `wiki/pages/*.md` never reached the repo. Moved generation into `commit_and_push` (after first `git add`, before commit) targeting `context.worktree_path / "wiki"`, made `git_diff_facts` diff the working tree, and converted swallowed failures into typed `WikiError` → `Awaiting Input`.

## Overview

- Wiki write in `finally` gated on `is_success` ran after `git commit`/`push`.
- Targeted `service.PAGES_ROOT` (main checkout), not the worktree branch — invisible to `git add`.
- `git_diff_facts` used `git diff <base_ref>..HEAD` (commit-to-commit), empty before next commit.

## Typed error + step

`demetra/library/exceptions.py` — `class WikiError(DemetraError)`. `demetra/library/models.py` — added `"wiki"` to `StepType`.

## Working-tree diff

`demetra/services/wiki/facts.py` — `git_diff_facts` now `git diff {base_ref}` (working tree vs base) so uncommitted build changes are documented before commit. Safe for merge/rebase (clean worktree post-merge → equivalent).

## Configurable wiki root

Helpers now accept optional target so main flow writes to worktree while merge/rebase keep legacy default:

- `demetra/services/wiki/parsing.py` — `existing_page_for_ticket(ticket_identifier, pages_root=None)`
- `demetra/services/wiki/index.py` — `read_index`/`write_index`/`patch_index`/`regenerate_by_topic` with `index_path=None`
- `demetra/services/wiki/render.py` — `write_session_wiki_page(context, wiki_root=None)`; writes to `<wiki_root>/pages/` + `<wiki_root>/INDEX.md`; now `raise WikiError(f"Failed to write wiki page for {identifier}: {e}")` instead of swallowed log. Re-exported via `demetra.services.wiki` facade.

## Wiki inside `commit_and_push`

`demetra/workflows/cleanup.py` — sequence: 1) `git add` build changes (bail `return False` if empty), 2) `update_session_step(..., step="wiki")` then `write_session_wiki_page(context, wiki_root=context.worktree_path / "wiki")` (WikiError aborts commit), 3) second `git add` stages `wiki/pages/*.md` + `wiki/INDEX.md`, 4) `git commit`/`push`/PR.

> **Status update (2026-08-28):** PR #106 (MNT-189) superseded deferred-raise: `commit_and_push` now never re-raises `WikiError` — on failure logs warning and returns `True` after successful `commit`/`push`/PR (`demetra/workflows/cleanup.py:137-141`). `process_wiki_failure` in `main.py:except WikiError` is unreachable from commit path; wiki is best-effort, no `Awaiting Input`. Test renamed `test_commit_and_push_wiki_failure_returns_true_after_successful_push` (`tests/test_workflows.py:1820`).

## Failure handling

`demetra/templates/wiki_failed.md` — `## Wiki page generation failed` template. `demetra/workflows/failure.py` — `process_wiki_failure(context, error)` via `notify_linear_failure(..., comment_label="wiki-failure")` → `Awaiting Input`. `main.py` — removed wiki from `finally`, added `except WikiError` before generic `DemetraError` → `process_wiki_failure` + `failure_step="awaiting_input"` (`should_update_linear_status=False`).

## Test Results

- `tests/test_wiki.py` — `test_failure_is_swallowed` → `test_failure_raises_wiki_error`; `test_writes_to_custom_wiki_root`; `git_diff_facts` asserts `diff <base_ref>` without `..HEAD`
- `tests/test_workflows.py` — `mock_commit_deps` with patched `write_session_wiki_page`; asserts wiki write with `wiki_root` + second `git_add_all`; `test_commit_and_push_wiki_failure_raises_wiki_error`
- `tests/test_entrypoints.py` — `test_main_writes_wiki_before_commit`, `test_main_handles_wiki_failure`
- `tests/test_failure.py` — `test_posts_wiki_failure_comment`

`899 passed in 23.56s`; `ruff`/`ty`/`bandit`/`pre-commit` clean.

## Follow-ups

- Merge/rebase still use legacy default root (clean post-merge, PR already carries page) — could unify to worktree root.
- `git_diff_facts` captures uncommitted changes pre-write; staged wiki files appearing in diff is benign.

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-05-pr-creation-failure-handler]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]], [[2026-08-07-split-wiki-service-into-subpackage]]
- External: [MNT-187](https://linear.app/mnt/issue/MNT-187/wiki-pages-not-generated)
