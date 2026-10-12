---
title:              Review agent models bypass the environment layers
date: 2026-10-12
type:               debug
status:             resolved
session_id:         ses_ed007e060ffetVuRkLGHUFJgwl
services:           [workflows, library]
branch:             master
tickets:            []
tags:               [environment, session-environment, review, opencode, settings]
related:            [2026-09-16-mnt-205-revise-merged-environment.md, 2026-10-06-unify-subprocess-env-on-session-environment.md, 2026-08-18-categorize-settings-env-vars-by-layer.md]
---

# Review agent models bypass the environment layers

## TL;DR

`OPENCODE_REVIEW_MODELS` was the last agent setting still read straight from
`demetra/settings.py`: `run_review_agents` iterated `OPENCODE["review_models"]`
instead of resolving through `SessionEnvironment`, so a project- or user-level
model list in the database was ignored for the review agents only. The cause
was an omission in the MNT-205 env rework, not a regression — review is the
only agent with an N-model fan-out (`list[str]`) while `SessionEnvironment`'s
API is single-valued, and the plural key never matched the generic
`_MODEL` suffix rule in `settings_default()`. Fixed by teaching
`settings_default()` the plural key, adding a `SessionEnvironment.review_models`
property, and iterating that in `run_review_agents`.

---

## Symptom

A project configured with its own review model list in the database still ran the
review agents on the three models baked into `demetra/settings.py`
(`opencode-go/qwen3.7-plus`, `opencode-go/glm-5.2`, `opencode-go/kimi-k2.7-code`).
Every other agent — plan, build, merge, rebase, resolve, validate, research —
honoured the `project → user-shared → settings` precedence, so the divergence
looked like a per-agent bug rather than a layering bug.

## Step 1 — Confirm every other agent resolves models through `SessionEnvironment`

`demetra/services/agents/opencode.py` takes `model` from the caller and only
falls back to settings when no environment is supplied:

```python
model=environment.opencode_<agent>_model if environment is not None else OPENCODE["<agent>_model"]
```

`SessionEnvironment` exposes exactly one property per single-model agent, and
`settings_default()` resolves them through a shared suffix rule
(`demetra/library/models.py`):

- `opencode_plan_model`
- `opencode_build_model` (also used by merge / rebase / review_fixes)
- `opencode_resolve_model`
- `opencode_validate_model`
- `opencode_research_model`

No review equivalent existed.

## Step 2 — The review workflow read the settings module directly

**File:** `demetra/workflows/review.py`

```python
from demetra.settings import OPENCODE          # module-level settings import

review_agents = []
for model in OPENCODE["review_models"]:        # ← the divergence
    review_agents.append(
        opencode_review_agent(target_path=target_path, model=model, environment=environment, project_id=project_id)
    )
```

`environment` *was* forwarded on the next line — but only so `run_command` could
build the **subprocess** env. The model selection itself bypassed the layers.
That split explains the confusing symptom: the project value of
`OPENCODE_REVIEW_MODELS` *did* reach the review-agent subprocess via
`subprocess_env`, yet demetra itself kept picking models from `settings.py`.

## Step 3 — Even `environment.get("OPENCODE_REVIEW_MODELS")` would have raised

`settings_default()` only handles the plural key through an explicit `match`
case, and the generic rule requires the `_MODEL` **singular** suffix:

```python
if key.startswith("OPENCODE_") and key.endswith("_MODEL"):
```

`OPENCODE_REVIEW_MODELS` ends in `_MODELS`, so it missed both arms and returned
`None` — meaning `get()` would raise `EnvironmentConfigError` rather than
silently returning the settings list. Both halves of the migration were
missing, not just the call site.

## Step 4 — Git history: an omission, not a regression

`git log --oneline -- demetra/workflows/review.py`:

- `74ea2d8` (2026-03-28) — introduced `from demetra.settings import OPENCODE`
  and the `OPENCODE["review_models"]` loop.
- `68e53b7` (2026-09-16, MNT-205) — added `SessionEnvironment` and converted
  **all five other** agents to `environment.opencode_*_model`. Line 55 was left
  untouched.
- `67d106c` (2026-10-06, MNT-161) — replaced the `env: dict` kwarg with
  `environment=SessionEnvironment`. Again only the call at line 57 was
  rewritten, not the loop head.

## Root cause

Two gaps that only became visible once the N-model fan-out met a single-valued
resolver API:

- **Structural.** Review is the only agent configured as a list
  (`OPENCODE["review_models"]: list[str]`). `SessionEnvironment`'s `lookup`/`get`
  are strictly `str -> str | None`, so there was no obvious target property to
  migrate to — and the migration was skipped rather than the API widened.
- **Documentation scope.** [[2026-08-18-categorize-settings-env-vars-by-layer]]
  lists `OPENCODE_REVIEW_MODELS` as a *System* layer variable, and its migration
  step only ever said "OpenCode models → user overrides" without calling out the
  plural list.

A corroborating detail: `tests/test_session_environment.py` already carried
`"review_models": ["settings/review-1", "settings/review-2"]` in its
`OPENCODE_SETTINGS` fixture — dead fixture data anticipating exactly this
property.

## Resolution / Fix

### Step 1 — Teach `settings_default()` the plural key

**File:** `demetra/library/models.py` — added to the `match key:` block:

```python
case "OPENCODE_REVIEW_MODELS":
    return ",".join(OPENCODE["review_models"])
```

Comma-joined because `settings_default` is `str -> str | None`; the separator
matches `env_get_list`, so a value written as `"custom/a,custom/b"` round-trips
consistently.

### Step 2 — Add the resolver property

**File:** `demetra/library/models.py` — alongside the other five model
properties:

```python
@property
def review_models(self) -> list[str]:
    return [model.strip() for model in self.get("OPENCODE_REVIEW_MODELS").split(",") if model.strip()]
```

### Step 3 — Use it in the workflow

**File:** `demetra/workflows/review.py`

```python
models = environment.review_models if environment is not None else OPENCODE["review_models"]
for model in models:
```

The `OPENCODE` import is retained purely as the `environment is None` fallback,
which keeps the existing `run_review_agents(target_path)`-without-environment
callers (and their tests) working.

## Test Results

- `tests/test_session_environment.py` — new `TestSessionEnvironmentReviewModels`:
  settings fallback, project-over-user precedence, user-layer read, blank-entry
  trimming.
- `tests/test_workflows.py` — `test_run_review_agents_uses_the_resolved_models`
  asserts the models handed to `opencode_review_agent` come from the project
  layer.
- Full suite: **951 passed**. `ruff check`, `ruff format --check` and
  `ty check` all clean.

---

## Follow-ups

- **`wiki/audits/workflow-state-machine.html`** still renders the review node as
  "parallel opencode_review_agent × review_models" without noting the layer
  resolution — cosmetic, not yet updated.
- **`origin/dev` already carries this fix** as `c7308e1` ("MNT-230: Add Claude
  Code harness support"), whose test docstring names this exact gap. The changes
  here were made on `master` independently and more narrowly; reconcile the two
  when the branches merge.
- No UI affordance lists the recognised model keys — `react/src/components/
  EnvSettings.tsx` and `EnvSettingsModal.tsx` are generic free-form key/value
  editors, so a typo in `OPENCODE_REVIEW_MODELS` now raises
  `EnvironmentConfigError` at review time rather than being caught in the modal.

## References

- Related: [[2026-09-16-mnt-205-revise-merged-environment]]
- Related: [[2026-10-06-unify-subprocess-env-on-session-environment]]
- Related: [[2026-08-18-categorize-settings-env-vars-by-layer]]