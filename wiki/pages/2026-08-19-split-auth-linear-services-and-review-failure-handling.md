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

On the MNT-170 env-layers branch, a follow-up refactor split the two remaining
monolithic service facades — `auth` and `linear` — into per-concern submodules
behind their `__init__.py` facades, and deleted the `sys.meta_path` relocation
shim from `demetra/services/__init__.py` (the last trace of the legacy flat
import paths). In parallel, review/PR-description LLM failures changed from
silent empty returns (`[]` / `""`) to typed exceptions (`ReviewError`,
`PrDescriptionError`) that route the ticket to `Awaiting Input` with a new
`review_failed` template. All 83 + 72 targeted tests pass.

---

## Overview

The MNT-170 branch (env-var layers) carried two distinct strands of work. The
committed `59637b4` did the migration itself; this session staged the follow-up
cleanup on top: service subpackage splits plus the review-failure error path.

## Step 1 — Split `auth` service into submodules

**File:** `demetra/services/auth/__init__.py` — the ~450-line single module was
reduced to a facade that re-exports via `__all__` and delegates to three new
modules:

- `demetra/services/auth/jwt.py` — `create_jwt_token`, `verify_jwt_token`
- `demetra/services/auth/oauth.py` — `get_github_auth_url`,
  `exchange_code_for_token`, `get_github_user`
- `demetra/services/auth/sessions.py` — `get_or_create_user`,
  `authenticate_user`, `signup_with_password`, `login_with_password`, `logout`,
  `get_current_user`, `get_current_user_dep`, `has_permission`,
  `reset_password`, `reset_password_cli`

The submodules read shared state through the facade at call time —
`import demetra.services.auth as service` then `service.JWT`,
`service.create_user`, `service.get_transaction`, etc. — so monkeypatch seams on
the facade keep holding. `sessions.py` keeps the two heavy imports
(`sqlalchemy`, `tui`) local to the functions that need them to break the import
cycle.

## Step 2 — Split `linear` service into submodules

**File:** `demetra/services/linear/__init__.py` — likewise reduced to a facade
re-exporting via `__all__`, delegating to:

- `demetra/services/linear/config.py` — `get_linear_config_value`
- `demetra/services/linear/mutations.py` — `update_ticket_status`,
  `post_comment`, `linear_cleanup`, `create_linear_ticket`
- `demetra/services/linear/tasks.py` — `get_linked_projects`,
  `extract_comments`, `extract_labels`, `get_todo_issues`,
  `get_linear_task_by_id`, `get_linear_task`

Same facade-at-call-time pattern (`import demetra.services.linear as service`
then `service.get_connection`, `service.print_message`, `service.get_query`).

## Step 3 — Remove the `services` relocation shim

**File:** `demetra/services/__init__.py` — the previous `sys.meta_path`-installed
`_RelocatedFinder` / `_RelocatedLoader` (which served the legacy flat import
paths like `demetra.services.git`, `demetra.services.groq`) was deleted. The
package is now a plain marker:

```python
"""Service layer package marker.

Individual services live in subpackages (e.g. ``auth``, ``linear``,
``vcs``) whose ``__init__.py`` acts as the public facade. This package
contains no executable code.
"""
```

This completes the subpackage migration begun with
[[2026-08-07-split-wiki-service-into-subpackage]] and the earlier
`vcs`/`agents`/`llm`/`persistence` splits. A grep confirms no remaining
`services.auth` / `services.linear` legacy references — only the facade imports
`demetra.services.auth` / `demetra.services.linear`.

## Step 4 — Extract the tools registry

**File:** `demetra/tools/__init__.py` / `demetra/tools/registry.py` — the
aggregating `list_tools` / `call_tool` dispatcher moved verbatim out of
`tools/__init__.py` into a new `registry.py`; the package `__init__` now only
re-exports them. No behaviour change.

## Step 5 — Review / PR-description failures become typed exceptions

Previously the OpenRouter summarization silently degraded: `summarize_review`
returned `[]` on LLM failure and `generate_pr_description` returned `""`, so a
broken review produced a passed review and an empty PR body.

**File:** `demetra/library/exceptions.py` — added two exceptions:

```python
class ReviewError(DemetraError):
    pass


class PrDescriptionError(DemetraError):
    pass
```

**File:** `demetra/services/llm/openrouter.py` —
`summarize_review` now `raise ReviewError("Failed to summarize the review")`,
`generate_pr_description` now `raise PrDescriptionError("Failed to generate the PR description")`
(was `return []` / `return ""`).

**File:** `demetra/workflows/cleanup.py` — `commit_and_push` catches
`PrDescriptionError` and re-raises as `PullRequestError`, so a failed PR body no
longer silently proceeds with an empty body.

**File:** `demetra/workflows/failure.py` — `process_pr_failure` was generalized
from `PullRequestError`-only to `DemetraError`. A `ReviewError` posts the new
`review_failed` template and labels the comment `review-failure`; everything else
keeps the existing `pr_creation_failed` template / `PR-creation-failure` label.
Both paths still move the ticket to `Awaiting Input`.

**File:** `demetra/templates/review_failed.md` — new template reporting that the
review agents ran but summarization failed, with the error and a request to
investigate.

**File:** `main.py` — a new `except ReviewError` handler delegates to
`process_pr_failure` and records the step as `awaiting_input`, mirroring the
existing `PullRequestError` handler
([[2026-08-05-pr-creation-failure-handler]]).

## Test Results

Targeted suites green:

```text
83 passed in 1.60s   # test_failure, test_openrouter, test_entrypoints, test_workflows
72 passed in 1.93s   # test_linear, test_auth
```

New coverage added:
- `tests/test_openrouter.py` — `summarize_review` raises `ReviewError`,
  `generate_pr_description` raises `PrDescriptionError` on LLM failure.
- `tests/test_failure.py` — `process_pr_failure` posts the `review_failed`
  comment with the error text and moves to `Awaiting Input`.
- `tests/test_entrypoints.py` — `main()` delegates a `ReviewError` from the
  build step to `process_pr_failure` + `awaiting_input` cleanup.
- `tests/test_workflows.py` — `run_review_agents` propagates `ReviewError`;
  `commit_and_push` raises `PullRequestError` when PR-description generation
  fails and never opens the PR.

---

## Consistency note (2026-08-20)

MNT-170 merged to `master` via PR #80 (`2026-08-19`). The auth/linear subpackage
split, tools registry extraction, review-failure exception path, and relocation-shim
removal are all on `master`. Allowlist logic lives at
`demetra/services/auth/allowlist.py` (not the legacy flat `demetra/services/allowlist.py`
path referenced in [[2026-08-06-allowlist-review-fixes]]).

## Follow-ups

- None.

## References

- Related: [[2026-08-07-split-wiki-service-into-subpackage]],
  [[2026-08-18-migrate-llm-groq-to-openrouter]],
  [[2026-08-05-pr-creation-failure-handler]],
  [[2026-08-06-allowlist-review-fixes]]
- External: [MNT-170](https://linear.app/mnt/issue/MNT-170/migrate-workflow-env-vars-to-projectuser-env-layers)
