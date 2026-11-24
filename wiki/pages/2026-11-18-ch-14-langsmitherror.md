---
title: 'CH-14: LangSmithError'
generated: {by: demetra, at: '2026-11-18T00:00:00Z'}
description: CH-14 standardised LangSmith tracing end to end — configuration now comes only from settings.py, tracing is off by default and needs both an API key and LANGSMITH_TRACING=true, and every container and subprocess traces into the single shared Demetra project.
type: implementation
status: stable
session_id: ses_e123b266affe6rM5I3Bfz3Rygi
services: [.env.docker, AGENTS, library, runtime/subprocess, settings, docker-compose, pyproject, test_docker_compose, test_opencode, test_session_environment, test_settings, test_subprocess, uv, .sessions, INDEX, 2026-11-17-langsmith-403-multipart-ingest]
branch: ch-14-langsmitherror
tickets: [CH-14]
tags: [wiki, infrastructure, bug]
related: [2026-11-17-langsmith-403-multipart-ingest.md, 2026-09-28-compose-langsmith-host-env.md, 2026-10-06-unify-subprocess-env-on-session-environment.md]
---

# CH-14: LangSmithError

## TL;DR

This session standardized LangSmith tracing configuration across the platform, making it opt-in and ensuring all traces go to a single shared project. The changes prevent partial configurations where tracing could be enabled without a valid API key, which was causing the `LangSmithError` in containers. Tracing is now disabled by default and requires both an API key and explicit `LANGSMITH_TRACING=true` to activate.

## Overview

The implementation consolidated LangSmith configuration to come only from `settings.py`, ignoring any project or user layer overrides. This ensures all containers and processes use the same tracing destination and prevents misconfigured tracing attempts.

## Step 1 — Update settings.py

**File:** demetra/settings.py:243-254

```python
_LANGSMITH_API_KEY = (env_get_str(name="LANGSMITH_API_KEY", default="") or "").strip()
_LANGSMITH_TRACING = bool(_LANGSMITH_API_KEY) and env_get_bool("LANGSMITH_TRACING", False)

LANGSMITH: LangSmithConfig = {
    "tracing": _LANGSMITH_TRACING,
    "api_key": _LANGSMITH_API_KEY or None,
    ...
}

if not _LANGSMITH_TRACING:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGSMITH_TRACING_V2"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
```

Changes:
- Tracing now requires both an API key and explicit `LANGSMITH_TRACING=true`
- A whitespace-only key counts as missing, and stored keys are stripped
- `langsmith`/`langchain-core` decide tracing from the process env, so the
  in-process flags are forced off when no key is configured

## Step 2 — Update SessionEnvironment.system_env

**File:** demetra/library/models.py:753-800

```python
def system_env(self):
    enabled = self._langsmith_tracing()
    return {
        "LANGSMITH_TRACING": enabled,
        "TRACE_TO_LANGSMITH": enabled,
        "LANGSMITH_ENDPOINT": settings_default("LANGSMITH_ENDPOINT") or "",
        "LANGSMITH_PROJECT": settings_default("LANGSMITH_PROJECT") or "",
        ...
    }

def tracing_env(self):
    if self._langsmith_tracing() != "true":
        return {}
    return {"LANGSMITH_API_KEY": settings_default("LANGSMITH_API_KEY") or ""}
```

Changes:
- Removed layer lookups for LangSmith variables
- All tracing configuration now comes from `settings.py` defaults
- The shared platform key stays out of `system_env` and is exposed only through
  `tracing_env`, so subprocesses running project code (git, lint, tests) never
  see it

## Step 3 — Update subprocess environment building

**File:** demetra/services/runtime/subprocess.py:32-95

```python
def build_subprocess_env(..., forward_tracing: bool = False):
    ...
    if environment is not None:
        merged_env.update(environment.subprocess_env)
        if forward_tracing:
            merged_env.update(environment.tracing_env)
```

Changes:
- Documented the platform-wide nature of the derived tracing vars
  (`LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`,
  `TRACE_TO_LANGSMITH`) and confirmed project/user layer overrides are
  intentionally ignored; other `LANGSMITH_*` keys are not filtered
- `LANGSMITH_API_KEY` is merged only for the agent run that emits traces
  (`run_opencode_agent` passes `forward_tracing=True`)

## Step 4 — Update default configuration

**File:** .env.docker.example:55-57

```python
# LangSmith tracing — one platform key/project is shared by all users and
# projects; the key must be authorized for the project below. Opt-in: tracing
# stays off unless a key is set here and LANGSMITH_TRACING is true.
LANGSMITH_TRACING=false
```

Changes:
- Changed default to `false`
- Added documentation about the opt-in requirement

## Test Results

All 1556 tests passed, confirming the changes maintain backward compatibility while fixing the tracing configuration issues.

## Follow-ups

- None

## References
- Related: [2026-11-17-langsmith-403-multipart-ingest](/pages/2026-11-17-langsmith-403-multipart-ingest.md) — the root-cause diagnosis of the 403 flood this session fixes (same branch)
- Related: [2026-09-28-compose-langsmith-host-env](/pages/2026-09-28-compose-langsmith-host-env.md) — the host→container forwarding these defaults build on
- Related: [2026-10-06-unify-subprocess-env-on-session-environment](/pages/2026-10-06-unify-subprocess-env-on-session-environment.md) — introduced `SessionEnvironment.system_env` / `tracing_env`
- External: <linear ticket URL>
