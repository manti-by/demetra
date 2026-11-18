---
title: 'CH-14: LangSmithError'
date: '2026-11-18'
type: implementation
status: resolved
session_id: ses_e123b266affe6rM5I3Bfz3Rygi
services: [.env.docker, AGENTS, library, runtime/subprocess, settings, docker-compose, pyproject, test_docker_compose, test_opencode, test_session_environment, test_settings, test_subprocess, uv, .sessions, INDEX, 2026-11-17-langsmith-403-multipart-ingest]
branch: ch-14-langsmitherror
tickets: [CH-14]
tags: [wiki, infrastructure, bug]
related: []
---

# CH-14: LangSmithError

## TL;DR

This session standardized LangSmith tracing configuration across the platform, making it opt-in and ensuring all traces go to a single shared project. The changes prevent partial configurations where tracing could be enabled without a valid API key, which was causing the `LangSmithError` in containers. Tracing is now disabled by default and requires both an API key and explicit `LANGSMITH_TRACING=true` to activate.

## Overview

The implementation consolidated LangSmith configuration to come only from `settings.py`, ignoring any project or user layer overrides. This ensures all containers and processes use the same tracing destination and prevents misconfigured tracing attempts.

## Step 1 — Update settings.py

**File:** demetra/settings.py:242-248

```python
_LANGSMITH_API_KEY = env_get_str("LANGSMITH_API_KEY", None)

LANGSMITH: LangSmithConfig = {
    "tracing": bool(_LANGSMITH_API_KEY) and env_get_bool("LANGSMITH_TRACING", False),
    "api_key": _LANGSMITH_API_KEY,
    ...
}
```

Changes:
- Tracing now requires both an API key and explicit `LANGSMITH_TRACING=true`
- Default tracing is `false` when either is missing

## Step 2 — Update SessionEnvironment.system_env

**File:** demetra/library/models.py:746-763

```python
class SessionEnvironment:
    # LangSmith tracing vars are platform-wide: they come only from the
    # ``settings.py`` defaults, never from the project or user layers
    tracing = settings_default("LANGSMITH_TRACING") == "true"
    api_key = settings_default("LANGSMITH_API_KEY") or ""
    
    return {
        "TRACE_TO_LANGSMITH": str(tracing and bool(api_key)),
        "LANGSMITH_API_KEY": api_key,
        "LANGSMITH_ENDPOINT": settings_default("LANGSMITH_ENDPOINT") or "",
        "LANGSMITH_PROJECT": settings_default("LANGSMITH_PROJECT") or "",
    }
```

Changes:
- Removed layer lookups for LangSmith variables
- All tracing configuration now comes from `settings.py` defaults

## Step 3 — Update subprocess environment building

**File:** demetra/services/runtime/subprocess.py:47-53

```python
# LangSmith vars are platform-wide, sourced only from ``settings.py``
# a project that opted a ``LANGSMITH_*`` key in via ``OS_ENV_PROJECT_OPTINS`` has it
# overridden here, and project/user layer ``LANGSMITH_*`` values are ignored.
# That is intended: all users and projects share one LangSmith project
```

Changes:
- Documented the platform-wide nature of LangSmith configuration
- Confirmed project/user layer overrides are intentionally ignored

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

All 1549 tests passed, confirming the changes maintain backward compatibility while fixing the tracing configuration issues.

## Follow-ups

- None

## References
- External: <linear ticket URL>
