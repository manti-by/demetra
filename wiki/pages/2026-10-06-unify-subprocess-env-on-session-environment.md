---
title:              Unify subprocess env on SessionEnvironment
date: 2026-10-06
type:               implementation
status:             resolved
session_id:         '-'
services: [subprocess, vcs, agents, quality, wiki, workflows]
branch:             '-'
tickets: []
tags: [environment, subprocess, session-environment, langsmith, refactor]
related: [2026-09-16-mnt-205-revise-merged-environment.md, 2026-08-10-process-environment-3-layers-encryption-uv-venv.md, 2026-09-28-compose-langsmith-host-env.md, 2026-08-18-categorize-settings-env-vars-by-layer.md]
---

# Unify subprocess env on SessionEnvironment

## TL;DR

The legacy `env: dict[str, str] | None` parameter that was threaded through `run_command`,
`run_command_to_file` and ~50 service helpers is gone. Every subprocess layer now takes
`environment: SessionEnvironment | None`, and *everything* a subprocess needs —
user-shared, project and the derived LangSmith tracing vars — is assembled by one
property: `SessionEnvironment.subprocess_env`. There is no second env channel: no `env`
dict, no `extra` override argument. This also fixed a real gap — `run_review_agents`
called `opencode_review_agent` **without** `environment`, so review agents ran with no
project/user layers and no tracing vars.

---

## Overview

Two mechanisms existed side by side:

1. **`context.environment`** — the `SessionEnvironment` resolver from
   [[2026-09-16-mnt-205-revise-merged-environment]] (project → user → settings), used for
   agent models, Linear settings, OpenRouter config and LangSmith tracing.
2. **`env: dict[str, str] | None`** — a raw dict passed down `run_command` → git / gh /
   quality / wiki helpers, assembled by callers as `context.project.environment`. Workflows
   had to pre-merge the layers themselves:
   `project.environment = {**project.user_environment, **project.environment}`.

Every agent wrapper took **both** (`opencode_review_agent(env=..., environment=...)`), so
the same subprocess received the project env twice under two different merge strategies,
and the call site decided which one won.

### Layer order after this change

| # | Layer | Source | Precedence |
|---|-------|--------|------------|
| 1 | OS allowlist (+ per-project opt-ins) | `filter_os_env(project_id)` | lowest |
| 2 | User-shared env | `SessionEnvironment.user_environment` | beats OS |
| 3 | Project env | `SessionEnvironment.project_environment` | beats user-shared |
| 4 | Derived LangSmith vars | `SessionEnvironment.system_env` | wins over raw layer values |
| 5 | `PWD` | `target_path` | always last |

Only one caller-supplied knob remains: `project_id`, which only widens the OS allowlist.

## Step 1 — `subprocess_env` becomes the single merge point

**File:** `demetra/library/models.py`

```python
@property
def subprocess_env(self) -> dict[str, str]:
    return {**self.user_environment, **self.project_environment, **self.system_env}
```

> **Consistency fix (2026-10-06, Consistency Agent):** the derived-vars property is
> `SessionEnvironment.system_env` (`demetra/library/models.py:482`), not `langsmith_env`
> as first written here — no `langsmith_env` attribute exists in code. The
> `subprocess_env` docstring at `models.py:407` still references
> `:attr:`langsmith_env`` and is stale the same way.

**File:** `demetra/services/runtime/subprocess.py`

`build_subprocess_env` lost its `user_environment` / `project_environment` keyword-only
parameters (they were only ever exercised by tests) and now takes the resolver:

```python
merged_env = filter_os_env(project_id=project_id)
if environment is not None:
    merged_env.update(environment.subprocess_env)
if target_path is not None:
    merged_env["PWD"] = str(target_path)
```

`run_command` and `run_command_to_file` pass `environment=environment` straight through;
`run_command_to_file` (`opencode export`) never needed more than that.

## Step 2 — `env` → `environment` everywhere

Renamed in `services/vcs/{git,github,merge,rebase}.py`,
`services/agents/{opencode,cursor,coderabbit}.py`, `services/quality/{lint,test}.py`,
`services/runtime/utils.py` (`is_package_installed`), `services/wiki/facts.py` and every
`workflows/*.py` call site. `perform_git_merge` / `perform_git_rebase` dropped their
separate `env` parameter entirely — they already carried `environment`.

The nine `opencode_*_agent` wrappers and `run_opencode_agent` lost the legacy parameter, so
each agent subprocess now gets the resolved environment:

**File:** `demetra/services/agents/opencode.py`

```python
return await run_command(
    command=command,
    target_path=target_path,
    disable_stdio=disable_stdio,
    environment=environment,
    input_text=task,
    project_id=project_id,
)
```

**File:** `demetra/workflows/review.py` — the bug this surfaced:

```python
# before: environment was never passed, so review agents got no layers and no tracing
opencode_review_agent(target_path=target_path, model=model, env=env, project_id=project_id)
# after
opencode_review_agent(target_path=target_path, model=model, environment=environment, project_id=project_id)
```

Session helpers (`get_opencode_sessions`, `get_opencode_session_id`,
`get_opencode_session_tokens`, `get_opencode_session_length`, `opencode_compact_session`)
and `git_default_branch` / `git_diff_facts` changed the same way; the wiki maintenance
call site dropped its `env=None`.

## Step 3 — drop the caller-side pre-merge

`setup.py`, `merge.py`, `rebase.py` and `review_fixes.py` no longer do

```python
project.environment = {**project.user_environment, **project.environment}
```

`Project.environment` holds only the project layer again and
`SessionEnvironment.subprocess_env` applies the precedence. Behaviour is unchanged: those
workflows build their `SessionEnvironment` from both layers, and
`Context.environment` does the same lazily.

`merge` / `rebase` / `review_fixes` now construct **one** `SessionEnvironment` right after
`setup_project_venv` and reuse it for `gh`, `git` and the agent, instead of rebuilding it
inline at the agent call.

## Step 4 — why there is no `extra` argument

The first pass threaded LangSmith vars through a new `extra: dict[str, str] | None` on
`run_command` (merged last, above every layer). That reintroduced exactly the second
channel this change set out to remove — a raw dict escaping next to `environment`, whose
precedence (`extra` > layers) had to be documented and tested separately.

Folding the derived vars into `SessionEnvironment.system_env` (merged inside
`SessionEnvironment.subprocess_env`) instead means:

- Callers have one argument and one mental model: "here is the resolved environment".
- Tracing resolution is always consistent, whether the subprocess is an agent, `git`, `gh`
  or `uv run pytest`.
- The "override wins over the raw layer" behaviour is a property of the environment
  (`subprocess_env`), not a parameter on the process launcher.

Safe for non-agent subprocesses: `system_env` resolves every key through
`SessionEnvironment.lookup` (the non-raising counterpart of `get`, treating an empty-string
layer value as unset) via the shared `env_get_*_from` helpers — see Step 5. That matters because `settings.py` builds these with
`env_get_str(name, default)`, which returns the raw value whenever the variable is *set* — so
`LANGSMITH_ENDPOINT=` in a `.env` reaches settings as `""`, not as the default. Without the
optional lookup, `get()` would raise and take down every subprocess launch, `git` included.
`system_env` also forces both flags off when no key is configured.

## Step 5 — one env-getter family for both `os.environ` and the layers

`SessionEnvironment.get_optional(key, default)` was a second, model-local implementation of
"read a variable, fall back on a default" — the job `services/runtime/utils.py` already does
for `settings.py` via `env_get_str` / `env_get_bool` / `env_get_list`. It is gone; the shared
helpers now take the resolver as an argument, and the `os.environ` wrappers delegate:

**File:** `demetra/services/runtime/utils.py`

```python
EnvGetter = Callable[[str], str | None]

def env_get_str_from(getter: EnvGetter, name: str, default: str | None) -> str | None: ...
def env_get_bool_from(getter: EnvGetter, name: str, default: bool) -> bool: ...

def env_get_bool(name: str, default: bool) -> bool:
    return env_get_bool_from(getter=os.environ.get, name=name, default=default)
```

`env_get_bool_from` also trims whitespace and treats an empty value as unset *without* a
warning, which is exactly what the layers need: `SessionEnvironment.lookup` never returns an
empty string, so `LANGSMITH_TRACING=` degrades to the default instead of warning on every
subprocess build.

**File:** `demetra/library/models.py` — `get_optional` became the non-raising
`lookup(key) -> str | None` (still skipping empty layer values), `get` raises when it returns
`None`, and `system_env` reads through the shared helpers:

```python
tracing = env_get_bool_from(getter=self.lookup, name="LANGSMITH_TRACING", default=False)
api_key = env_get_str_from(getter=self.lookup, name="LANGSMITH_API_KEY", default="")
```

`env_get_bool_from` / `env_get_str_from` are imported *inside* `system_env` because
`library/` is the pure layer and must not depend on `services/` at import time — the same
reason `_settings_default` imports `settings` lazily. `env_get_int`, `env_get_list` and
`env_get_path` still read `os.environ` directly; no caller needs a resolver variant of those
yet.

## Files touched

| Area | Files |
|------|-------|
| Library | `library/models.py`, `library/constants.py` |
| Runtime | `services/runtime/subprocess.py`, `services/runtime/utils.py` |
| VCS | `services/vcs/{git,github,merge,rebase}.py` |
| Agents | `services/agents/{opencode,cursor,coderabbit}.py` |
| Quality | `services/quality/{lint,test}.py` |
| Wiki | `services/wiki/{facts,maintenance,render}.py` |
| Workflows | `setup`, `plan`, `build`, `validate`, `review`, `review_fixes`, `resolve`, `research`, `lint`, `postprocess`, `cleanup`, `merge`, `rebase` |

## Test Results

- `uv run pytest tests/` — 936 passed
- `uv run ruff check .`, `uv run ruff format .`, `uv run ty check`, `uv run pre-commit run --all-files` — clean

Coverage changes:

- `TestSessionEnvironmentSubprocessEnv` (new): layer precedence, empty layers still
  resolving the tracing vars, derived vars overriding the raw layers, configured tracing
  reaching the mapping, and no mutation of the source layer dicts.
- `TestSessionEnvironmentLookup` (was `...GetOptional`): resolved value, `None` for an unset
  key, empty layer value treated as unset, the contrast with `get` raising, and an optional
  key resolved through `env_get_str_from`.
- `tests/test_utils.py`: resolver variants — `env_get_str_from` / `env_get_bool_from` over a
  plain dict (value, missing key, kept-empty string, whitespace, invalid + warning) and
  `env_get_bool` returning the default for an empty variable.
- `TestSessionEnvironmentLangSmith`: added empty-settings and empty-project-layer cases
  asserting no `EnvironmentConfigError`, plus the accepted truthy/falsy spellings.
- `TestBuildSubprocessEnv`: `extra` cases replaced by tracing-var cases
  (`test_derived_tracing_vars_are_forwarded_without_extra_arguments`,
  `test_derived_tracing_vars_win_over_the_project_layer`); merge-order test renamed to
  `test_merge_order_os_user_project`.
- `TestRunOpencodeAgentLangSmithEnv`: asserts `environment` is the only env argument and
  that the tracing vars travel inside it.
- `test_setup_workflow_merges_user_env_under_project_env` →
  `test_setup_workflow_layers_user_env_under_project_env`, now asserting
  `context.environment.subprocess_env` rather than a pre-merged `project.environment`.

---

## Follow-ups

- **Credential surface widened.** `subprocess_env` always emits `LANGSMITH_API_KEY` (resolved
  from `settings.py`, i.e. the *platform's* key) into every subprocess, including
  `uv run pytest` and arbitrary commands the build agent runs inside the target project's
  worktree. Previously `OS_ENV_ALLOWLIST` dropped it. A build agent or a project test that
  reads `env` can now see the platform credential. Unresolved by design for this change;
  scoping the derived vars to the agent launchers, or omitting the whole block when tracing
  is off, would restore the old surface.
- Related: the same unconditional injection writes `LANGSMITH_TRACING=false` and
  `LANGSMITH_PROJECT=Demetra` into the child's env, which *disables* tracing for a target
  project that instruments itself with LangSmith. Emitting only when enabled avoids it.
- The derived vars always win over the OS layer, so a project that opted a `LANGSMITH_*` key
  in via `OS_ENV_PROJECT_OPTINS` would have it silently overridden. Documented in
  `build_subprocess_env`; intended, since a `LANGSMITH_TRACING` flag without a key is worse
  than tracing being off.
- `run_validate_agent`, `run_review_agents` and `run_lint_and_test` are now keyword-only past
  their first argument, so a future parameter insertion cannot silently rebind a positional
  call (they all lost `env` from the middle of their signature in this change).
- `Project.environment` is mutated by `setup_project_venv` to inject
  `VIRTUAL_ENV` / `UV_PROJECT_ENVIRONMENT` / `UV_PATH` / `PATH`; that mutation now lands in
  the project layer that `subprocess_env` forwards everywhere. It works, but a dedicated
  venv layer (or an `extra`-free `venv_env` property) would be cleaner than smuggling
  them through the project env.

## References

- Related: [[2026-09-16-mnt-205-revise-merged-environment]]
- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Related: [[2026-09-28-compose-langsmith-host-env]]
- Related: [[2026-08-18-categorize-settings-env-vars-by-layer]]
