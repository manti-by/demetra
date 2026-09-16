---
title: Split auth/linear services into subpackages + review-failure handling
date: 2026-08-19
type: implementation
status: resolved
session_id: "-"
services: [auth, linear, tools, llm, workflows]
branch: feature/mnt-170-migrate-workflow-env-vars-to-projectuser-env-layers
tickets: [MNT-170]
tags: [refactor, subpackage, facade, exceptions, review, pr-description, openrouter]
related: [2026-08-05-pr-creation-failure-handler.md, 2026-08-06-allowlist-review-fixes.md, 2026-08-07-split-wiki-service-into-subpackage.md, 2026-08-18-migrate-llm-groq-to-openrouter.md]
---

# Split auth/linear services into subpackages + review-failure handling

## TL;DR

On the MNT-170 branch (merged via PR #80, 2026-08-19), the `auth` and `linear` monolithic facades were split into per-concern submodules behind `__init__.py` facades and the `sys.meta_path` relocation shim was deleted from `demetra/services/__init__.py`. In parallel, `summarize_review`/`generate_pr_description` now raise typed `ReviewError`/`PrDescriptionError` → `Awaiting Input` with a `review_failed` template instead of silently returning `[]`/`""`. 83 + 72 tests pass.

## Overview

Branch `59637b4` did the env-layers migration; this session staged the follow-up cleanup: service splits plus the review-failure error path.

## Auth split

`demetra/services/auth/__init__.py` (~450 lines) → facade re-exporting via `__all__` to three modules:

- `demetra/services/auth/jwt.py` — `create_jwt_token`, `verify_jwt_token`
- `demetra/services/auth/oauth.py` — `get_github_auth_url`, `exchange_code_for_token`, `get_github_user`
- `demetra/services/auth/sessions.py` — `get_or_create_user`, `authenticate_user`, `signup_with_password`, `login_with_password`, `logout`, `get_current_user`, `get_current_user_dep`, `has_permission`, `reset_password`, `reset_password_cli`

Submodules read shared state via `import demetra.services.auth as service` (`service.JWT`, `service.get_transaction`, etc.) so facade monkeypatches still hold. Heavy imports (`sqlalchemy`, `tui`) kept local to break cycles.

## Linear split

`demetra/services/linear/__init__.py` → facade delegating to:

- `demetra/services/linear/config.py` — `get_linear_config_value`
- `demetra/services/linear/mutations.py` — `update_ticket_status`, `post_comment`, `linear_cleanup`, `create_linear_ticket`
- `demetra/services/linear/tasks.py` — `get_linked_projects`, `extract_comments`, `extract_labels`, `get_todo_issues`, `get_linear_task_by_id`, `get_linear_task`

Same `import demetra.services.linear as service` pattern.

## Relocation shim removal

`demetra/services/__init__.py` — deleted `_RelocatedFinder`/`_RelocatedLoader` (`sys.meta_path`) that served legacy flat imports (`demetra.services.git`, `demetra.services.groq`). Now a plain marker package. Completes migration begun in [[2026-08-07-split-wiki-service-into-subpackage]] and the `vcs`/`agents`/`llm`/`persistence` splits.

## Tools registry

`demetra/tools/registry.py` extracted from `demetra/tools/__init__.py` — aggregating `list_tools`/`call_tool` moved verbatim; package `__init__` now only re-exports. No behaviour change.

## Review/PR-description typed failures

Previously `summarize_review` → `[]` and `generate_pr_description` → `""` on LLM failure, silently passing review / empty PR body.

- `demetra/library/exceptions.py` — added `ReviewError(DemetraError)` and `PrDescriptionError(DemetraError)`
- `demetra/services/llm/openrouter.py` — `summarize_review` raises `ReviewError("Failed to summarize the review")`, `generate_pr_description` raises `PrDescriptionError(...)`
- `demetra/workflows/cleanup.py` — `commit_and_push` catches `PrDescriptionError` → re-raises `PullRequestError`
- `demetra/workflows/failure.py` — `process_pr_failure` generalized from `PullRequestError`-only to `DemetraError`; `ReviewError` posts `review_failed` template (`review-failure` label), else `pr_creation_failed` (`PR-creation-failure` label); both move to `Awaiting Input`
- `demetra/templates/review_failed.md` — new template
- `main.py` — added `except ReviewError` → `process_pr_failure` with `awaiting_input` (mirrors [[2026-08-05-pr-creation-failure-handler]])

## Test Results

```
83 passed in 1.60s   # test_failure, test_openrouter, test_entrypoints, test_workflows
72 passed in 1.93s   # test_linear, test_auth
```

New coverage: `test_openrouter` (ReviewError/PrDescriptionError on LLM failure), `test_failure` (`review_failed` comment → Awaiting Input), `test_entrypoints` (ReviewError delegation), `test_workflows` (review propagation, PR-description failure).

## Consistency note (2026-08-23)

Merged to `master` via PR #80. `render.py` TODO at `demetra/services/wiki/render.py:57` still present. Allowlist now at `demetra/services/auth/allowlist.py` (see [[2026-08-06-allowlist-review-fixes]]).

## Follow-ups

- ~~Complete MNT-170 review gates before commit~~ **Done** — merged via PR #80.
- Confirm whether `demetra/services/wiki/render.py` `# TODO: Add template and render` is deliberate or leftover.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]], [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-08-05-pr-creation-failure-handler]], [[2026-08-06-allowlist-review-fixes]]
- External: [MNT-170](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers)

> **Status update (2026-09-16, MNT-205):** `demetra/services/linear/config.py`
> (`get_linear_config_value`) and `demetra/services/llm/config.py`
> (`get_openrouter_config`) were deleted; resolution moved to
> `SessionEnvironment` / `context.environment`. See
> [[2026-09-16-mnt-205-context-environment]].
