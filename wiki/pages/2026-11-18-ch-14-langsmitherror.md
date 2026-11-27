---
title: 'CH-14: LangSmithError'
generated: {by: demetra, at: '2026-11-18T00:00:00Z'}
description: CH-14 diagnosed the worker.log 403 /runs/multipart flood from compose forcing LANGSMITH_TRACING=true with an unauthorized key and standardised LangSmith tracing end to end — configuration comes only from settings.py, tracing is opt-in and requires a valid key, and LANGSMITH_API_KEY is isolated to SessionEnvironment.tracing_env.
type: implementation
status: stable
session_id: ses_e123b266affe6rM5I3Bfz3Rygi
services: [settings, library, runtime, deploy, llm]
branch: ch-14-langsmitherror
tickets: [CH-14]
tags: [wiki, infrastructure, bug, langsmith, docker, compose, tracing, 403, environment, credentials]
related: [2026-09-28-compose-langsmith-host-env.md, 2026-10-06-unify-subprocess-env-on-session-environment.md, 2026-11-15-mnt-314-linear-mcp-static-api-key.md]
---

# CH-14: LangSmithError

## TL;DR

Traced the `WARNING: Failed to send compressed multipart ingest: langsmith.utils.LangSmithError` flood in `worker.log` (~157 occurrences on 2026-11-17) to HTTP `403 Forbidden` responses on `POST https://api.smith.langchain.com/runs/multipart`: `docker-compose.yaml` forced `LANGSMITH_TRACING=true` across every container while the forwarded `lsv2_pt_` personal token was unauthorized, turning on LangChain auto-instrumentation for internal `ChatOpenAI` calls. Standardized LangSmith tracing across the platform so configuration comes solely from `settings.py` (ignoring project/user layers), tracing is opt-in (`False` by default) and requires a non-empty API key, and the shared `LANGSMITH_API_KEY` is exposed only through `SessionEnvironment.tracing_env` (`forward_tracing=True`) rather than `system_env`.

## Overview

`CH-14` combined root-cause diagnosis of the container log flood with a platform-wide consolidation of LangSmith configuration (initially recorded across two write-ups on the `ch-14-langsmitherror` branch and merged here; post-review refinements landed in PR #164 / `4105ae2`).

## Symptom & Diagnosis

In `/var/log/demetra/worker.log` (2026-11-17, 07:49 → 20:15), ~157 warnings appeared in two variants from the SDK's background batch-ingest thread (`langsmith==0.10.16`, `client.py:3588` `_multipart_ingest` and `client.py:3672` `_send_compressed_multipart_req`), never failing a workflow:

- `WARNING: Failed to multipart ingest runs: langsmith.utils.LangSmithError: Failed to POST https://api.smith.langchain.com/runs/multipart in LangSmith API. HTTPError('403 Client Error: Forbidden for url: ...', '{"error":"Forbidden"}\n')`
- `WARNING: Failed to send compressed multipart ingest: langsmith.utils.LangSmithError: ...` (same 403)

Investigation established three compounding factors:

1. **Forced container flag (`docker-compose.yaml:6-9`):** the `x-demetra-env` anchor pre-seeded `LANGSMITH_TRACING=true`, `LANGSMITH_ENDPOINT`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT=Demetra` into every service. Demetra's internal LLM calls use `ChatOpenAI` (`langchain_openai`), which auto-instruments whenever `LANGSMITH_TRACING=true` is in the process environment. A `/proc/<pid>/environ` check confirmed PID 1 (`python -m demetra.worker`), `main.py`, `opencode run`/`serve`, the Demetra MCP server, and `wi` all carried `LANGSMITH_TRACING=true` and the same key (`TRACE_TO_LANGSMITH=true` on subprocesses).
2. **Unauthorized credential:** read-only probes with the forwarded `lsv2_pt_...` token returned HTTP 403 on `/api/v1/workspaces`, `/api/v1/runs`, and `/api/v1/datasets` (`api.eu.smith.langchain.com` did not resolve). Rotating the key is an operator action; code stops spurious ingests when the flag is off or the key is absent.
3. **Layer drift (`SessionEnvironment.system_env`):** `demetra/library/models.py` previously resolved the LangSmith key and project through project → user-shared → settings layers, allowing different projects or users to trace into inconsistent destinations instead of one shared platform project.

## Step 1 — Update settings.py

**File:** `demetra/settings.py:249-262`

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
- `langsmith`/`langchain-core` decide tracing from the process env, so the in-process flags are forced off when tracing is disabled or no key is configured

## Step 2 — Update SessionEnvironment.system_env and tracing_env

**File:** `demetra/library/models.py:827-880`

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
- Removed project/user layer lookups for LangSmith variables; all tracing configuration comes from `settings.py` defaults
- The pre-review draft placed `LANGSMITH_API_KEY` inside `system_env`; PR #164 (`4105ae2`) moved the shared platform key out of `system_env` into `tracing_env`, so subprocesses running project code (`git`, lint, tests) never see it

## Step 3 — Update subprocess environment building

**File:** `demetra/services/runtime/subprocess.py:32-95`

```python
def build_subprocess_env(..., forward_tracing: bool = False):
    ...
    if environment is not None:
        merged_env.update(environment.subprocess_env)
        if forward_tracing:
            merged_env.update(environment.tracing_env)
```

Changes:
- Documented the platform-wide nature of the derived tracing vars (`LANGSMITH_TRACING`, `LANGSMITH_ENDPOINT`, `LANGSMITH_PROJECT`, `TRACE_TO_LANGSMITH`) and confirmed project/user layer overrides are intentionally ignored; other `LANGSMITH_*` keys are not filtered
- `LANGSMITH_API_KEY` is merged only for the agent run that emits traces (`run_opencode_agent` passes `forward_tracing=True`)

## Step 4 — Update default configuration

**Files:** `docker-compose.yaml:6`, `.env.docker.example:55-57`

```python
# LangSmith tracing — one platform key/project is shared by all users and
# projects; the key must be authorized for the project below. Opt-in: tracing
# stays off unless a key is set here and LANGSMITH_TRACING is true.
LANGSMITH_TRACING=false
```

Changes:
- Flipped `docker-compose.yaml` `x-demetra-env` interpolation to `${LANGSMITH_TRACING:-false}` (opt-in)
- Updated `.env.docker.example` default to `false` and documented the single shared platform key/project requirement (`make deploy` / `make docker-up` pass `--env-file .env.docker`, so the deployed `.env.docker` controls the container value)

## Test Results

- `uv run pytest tests/` — all **1556** tests passed (including updated `test_settings`, `test_session_environment`, `test_subprocess`, `test_opencode`, and `test_docker_compose` suites)
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run ty check`, `uv run bandit -c pyproject.toml .`, `uv run pre-commit run --all-files`, and `make check-compose` — all clean

## Follow-ups

- Rotate / authorize `LANGSMITH_API_KEY` for the shared `Demetra` project and update the deployed host `.env.docker` (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`) before enabling tracing in production.

## References

- Related: [Forward LangSmith env vars from host to containers](/pages/2026-09-28-compose-langsmith-host-env.md) — the host→container forwarding these defaults build on
- Related: [Unify subprocess env on SessionEnvironment](/pages/2026-10-06-unify-subprocess-env-on-session-environment.md) — introduced `SessionEnvironment.system_env`
- Related: [MNT-314 — Linear MCP static API key](/pages/2026-11-15-mnt-314-linear-mcp-static-api-key.md) — sibling `SessionEnvironment.system_env` credential scoping change
- External: CH-14 (chat task; PR #164)
