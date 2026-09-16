---
title: MNT-205 — Revise merged environment: context.environment resolver
date: 2026-09-16
type: implementation
status: resolved
session_id: "-"
services: [library, opencode, linear, llm, workflows, daemons]
branch: mnt-205-revise-merged-environment
tickets: [MNT-205]
tags: [environment, settings, opencode, linear, openrouter, resolver]
related: [2026-08-18-categorize-settings-env-vars-by-layer.md, 2026-08-10-process-environment-3-layers-encryption-uv-venv.md, 2026-09-01-mnt-177-research-loop.md, 2026-06-08-project-environment.md]
---

# MNT-205 — Revise merged environment: context.environment resolver

## TL;DR

Three near-duplicate resolvers — `_resolve_opencode_model` (per-agent models),
`get_linear_config_value` (Linear state/team ids) and `get_openrouter_config`
(OpenRouter key/model) — each re-implemented the same "project env → user-shared
env → settings" fallback with slightly different code. They are replaced by a
single `SessionEnvironment` dataclass in `demetra/library/models.py`, exposed as
`Context.environment`. A missing key now raises `EnvironmentConfigError` instead
of silently resolving to an empty/None value. All workflow, daemon, Linear and
LLM call sites read from `context.environment`; the deleted `linear/config.py`
and `llm/config.py` modules are gone. Full suite 982 passed; ruff / ty / bandit
clean.

---

## Overview

Before this change the same fallback chain existed in at least three places:

- `demetra/services/agents/opencode.py` — `_resolve_opencode_model(value, key, user_environment)`:
  looked up `OPENCODE_<AGENT>_MODEL` in the user-shared env, else the settings default.
- `demetra/services/linear/config.py` — `get_linear_config_value(name, user_id)`:
  mapped a state/config name to `LINEAR_STATE_<NAME>_ID` / `LINEAR_<NAME>` and
  loaded the user env from the DB before falling back to settings.
- `demetra/services/llm/config.py` — `get_openrouter_config(user_id)`:
  loaded the user env and merged `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` over settings.

Each was threaded separately through helpers (`user_environment=` kwargs,
`user_id=` kwargs, DB loads inside helpers), so every new overrideable key meant
touching several layers. MNT-205 standardizes them into one resolver.

## Step 1 — `SessionEnvironment` resolver

**File:** `demetra/library/models.py`

`SessionEnvironment(project_environment, user_environment)` resolves a key in
order: project env → user-shared env → `settings.py` default. An empty string
is treated as missing, so it falls through to the next layer. If no layer
defines the key the resolver raises `EnvironmentConfigError` (new
`DemetraError` subclass in `demetra/library/exceptions.py`), which bubbles into
the existing workflow failure/cleanup path — no silent empty values.

```python
def get(self, key: str) -> str:
    if value := self.project_environment.get(key):
        return value
    if value := self.user_environment.get(key):
        return value
    if value := _settings_default(key):
        return value
    raise EnvironmentConfigError(f"Environment key {key!r} is not configured")
```

Typed accessors wrap `get`:

- `opencode_plan_model` / `opencode_build_model` / `opencode_resolve_model` /
  `opencode_validate_model` / `opencode_research_model`.
- `openrouter_config` (`OpenRouterConfig`; `base_url` always from settings).
- `linear_state(name)` → `LINEAR_STATE_<NAME>_ID`.
- `linear_value(name)` → `LINEAR_<NAME>` (`default_state` → `LINEAR_DEFAULT_STATE_ID`).

`_settings_default(key)` maps keys onto the existing `OPENCODE` / `OPENROUTER` /
`LINEAR` settings dicts and is imported lazily inside the function so the pure
library layer does not read configuration at import time. No new settings were
added to `settings.py`.

## Step 2 — `Context.environment`

**File:** `demetra/library/models.py`

```python
@property
def environment(self) -> SessionEnvironment:
    if self._environment is None:
        self._environment = SessionEnvironment(
            project_environment=self.project.environment,
            user_environment=self.project.user_environment,
        )
    return self._environment
```

Constructed lazily from the project's cached env dicts and cached on the
context. `setup_workflow` still pre-merges user-shared over project into
`project.environment` for subprocess use; the resolver keeps both layers so the
precedence is explicit.

## Step 3 — OpenCode agents

**File:** `demetra/services/agents/opencode.py`

`_resolve_opencode_model` is deleted. Every `opencode_*_agent` helper takes
`environment: SessionEnvironment | None = None` instead of `user_environment`
and resolves its model as
`environment.opencode_<agent>_model if environment is not None else OPENCODE["<agent>_model"]`.

## Step 4 — Linear helpers

**File:** `demetra/services/linear/` (`config.py` deleted)

`get_linear_config_value` is removed from the facade. `linear_cleanup` reads
`context.environment.linear_state(...)` and converts a missing state into the
existing `LinearError("Linear state '…' is not configured")`. The no-context
paths (`create_linear_ticket`, `get_todo_issues`, the watcher) load the
user-shared env explicitly and build a `SessionEnvironment(project_environment={}, user_environment=...)`.
The watcher's `_resolve_linear_state` helper maps `EnvironmentConfigError` to
`None` so it keeps its log-and-continue behavior.

## Step 5 — LLM helpers

**Files:** `demetra/services/llm/config.py` (deleted), `factory.py`, `openrouter.py`

`get_openrouter_config` is removed. `build_llm(..., environment=...)` reads
`environment.openrouter_config`, falling back to a settings-only
`SessionEnvironment` when omitted. `extract_questions`, `summarize_review`,
`process_text_with_openrouter`, `extract_plan`, `summarize_session` and
`generate_pr_description` take `environment` instead of `user_id`.

## Step 6 — Call sites

`workflows/build.py`, `plan.py`, `resolve.py`, `research.py`, `failure.py`,
`merge.py`, `rebase.py`, `review.py`, `review_fixes.py`, `cleanup.py`,
`services/wiki/render.py` and `main.py` pass `environment=context.environment`.
The merge/rebase/review-fixes workflows build a `SessionEnvironment` directly
from the loaded project. `perform_git_merge` / `perform_git_rebase` and
`run_validate_agent` take `environment`.

## Step 7 — Tests

- New `tests/test_session_environment.py`: layer precedence, settings fallback,
  empty-string fallthrough, `EnvironmentConfigError`, every typed accessor and
  `Context.environment` caching.
- `tests/test_settings_layers.py` rewritten around `build_llm` wiring.
- `tests/test_opencode.py`, `tests/test_openrouter.py`,
  `tests/test_validate_workflow.py`, `tests/test_workflows.py`,
  `tests/test_linear.py`, `tests/test_api_coverage.py`,
  `tests/test_more_coverage.py` updated to the new signature.

## Test Results

`uv run pytest tests/` → **982 passed**. `uv run ruff check .`,
`uv run ty check`, `uv run bandit -c pyproject.toml -r .` all clean.

## Follow-ups

- `users.keys` remains a vestigial per-user API-key field (unchanged here).

## References

- Related: [[2026-08-18-categorize-settings-env-vars-by-layer]], [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Related: [[2026-09-01-mnt-177-research-loop]], [[2026-06-08-project-environment]]
- External: [MNT-205 — Revise merged environment](https://linear.app/mnt/issue/MNT-205)
