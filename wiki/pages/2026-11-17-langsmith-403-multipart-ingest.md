---
title: LangSmith 403 multipart ingest — root cause and fix
date: 2026-11-17
type: debug
status: resolved
session_id: ses_e14d62ce4ffe3y0E5hTt9mu9PL
services: [settings, library, runtime, deploy, llm]
branch: ch-14-langsmitherror
tickets: []
tags: [langsmith, docker, compose, tracing, 403, environment, credentials]
related: [2026-09-28-compose-langsmith-host-env.md, 2026-10-06-unify-subprocess-env-on-session-environment.md, 2026-11-15-mnt-314-linear-mcp-static-api-key.md]
---

# LangSmith 403 multipart ingest — root cause and fix

## TL;DR

The `WARNING: Failed to send compressed multipart ingest: langsmith.utils.LangSmithError` flood in `worker.log` was a `403 Forbidden` on `POST https://api.smith.langchain.com/runs/multipart`: the Python `langsmith` SDK auto-traces Demetra's `ChatOpenAI` calls in every container because `docker-compose.yaml` forced `LANGSMITH_TRACING=true`, and the forwarded `lsv2_pt_` key is not authorized (403 on every LangSmith API endpoint). The fix makes LangSmith one platform-wide configuration — tracing is opt-in and gated on a configured key, and `SessionEnvironment.system_env` reads all `LANGSMITH_*` values only from `settings.py`, ignoring project/user layers — so all users and projects trace into one shared `Demetra` project and no subprocess ingests with a bad or empty key. Rotating the key remains an ops task; code only stops the spurious attempts.

---

## Symptom

`/var/log/demetra/worker.log`, 2026-11-17 (07:49 → 20:15, across many sessions), ~157 occurrences of one failure in two variants:

- `WARNING: Failed to multipart ingest runs: langsmith.utils.LangSmithError: Failed to POST https://api.smith.langchain.com/runs/multipart in LangSmith API. HTTPError('403 Client Error: Forbidden for url: ...', '{"error":"Forbidden"}\n')`
- `WARNING: Failed to send compressed multipart ingest: langsmith.utils.LangSmithError: ...` (same 403)

The warnings appeared around agent invocations (plan/build agents, LLM calls) but never failed a workflow — they are emitted by the SDK's background batch-ingest thread.

## Step 1 — Extract every error variant from the logs

- `grep` over `worker.log` found only the two variants above; both share the same cause and endpoint (`client.py:3588` `_multipart_ingest`, `client.py:3672` `_send_compressed_multipart_req` in `langsmith==0.10.16`).
- All returned `HTTPError('403 Client Error: Forbidden', '{"error":"Forbidden"}')` — an authorization rejection, not a network/timeout/serialization fault.

## Step 2 — Find what drives the SDK in containers

- **`docker-compose.yaml:6-9`** (the `x-demetra-env` anchor, merged into every service) forwarded `LANGSMITH_TRACING=true`, `LANGSMITH_ENDPOINT`, `LANGSMITH_API_KEY`, and `LANGSMITH_PROJECT=Demetra` into all containers.
- Demetra's own LLM calls use `ChatOpenAI` from `langchain_openai` (`demetra/services/llm/factory.py:1,48`), which is LangChain/LangSmith auto-instrumented. With `LANGSMITH_TRACING=true` in the process environment, every internal LLM call creates a run that the SDK batches to `/runs/multipart`.
- A `/proc/<pid>/environ` scan confirmed PID 1 (`python -m demetra.worker`), the `main.py` workflow process, `opencode run`/`serve`, the Demetra MCP server, and `wi` all carried `LANGSMITH_TRACING=true`, the same key (sha256 prefix `37a1b7c59fe5`), endpoint, and project. Subprocesses additionally carried `TRACE_TO_LANGSMITH=true`.
- **`SessionEnvironment.system_env`** (`demetra/library/models.py:743-769`) resolved the LangSmith key/project through the project → user-shared → settings layers, so different projects/users could trace with different keys into different projects rather than one shared project.

## Step 3 — Probe the credential

- Read-only requests with the forwarded key (`lsv2_pt_...`, 51 chars — a personal token) returned HTTP 403 on `/api/v1/workspaces`, `/api/v1/runs`, and `/api/v1/datasets`. The `api.eu.smith.langchain.com` endpoint did not resolve.
- Conclusion: the key itself is invalid/unauthorized for this project/region. Code cannot repair a rejected credential — an operator must rotate it (see Follow-ups). The in-repo fix removes the conditions that make a bad/absent key generate a log flood.

## Root cause

- **Trigger:** `LANGSMITH_TRACING=true` pre-seeded in every container by compose turned on LangChain auto-instrumentation of internal LLM calls, producing background trace ingests.
- **Failure:** the forwarded `lsv2_pt_` key is unauthorized, so each batch POST to `/runs/multipart` returned 403 and the SDK logged a warning.
- **Amplifier:** `SessionEnvironment.system_env` let project/user env layers override the key/project, so the identity of the traced project was not consistent across users and projects.

## Resolution / Fix

- **`demetra/settings.py:243`** — `api_key` is read first and `tracing` is `bool(api_key) and env_get_bool("LANGSMITH_TRACING", False)`; an absent/empty key can never enable auto-tracing. Endpoint and project keep their single shared defaults.
- **`demetra/library/models.py:743`** — `SessionEnvironment.system_env` now reads all five `LANGSMITH_*` values through `settings_default(...)` only. Project/user layer overrides are ignored; every user and project uses the one platform configuration. `TRACE_TO_LANGSMITH` still mirrors `LANGSMITH_TRACING`.
- **`demetra/services/runtime/subprocess.py:45`** — docstring updated: derived tracing vars are platform-wide and win over OS/project layers by design.
- **`docker-compose.yaml:6`** — `LANGSMITH_TRACING` default flipped to `${LANGSMITH_TRACING:-false}` (opt-in).
- **`.env.docker.example:55`** — sets `LANGSMITH_TRACING=false` and documents that one platform key/project is shared by all users and projects.
- Deploy nuance: `make deploy` / `make docker-up` pass `--env-file .env.docker`, so the compose interpolation reads the deployed `.env.docker`; that file's `LANGSMITH_TRACING` must be false/absent (or the key rotated) for the opt-in to take effect.

## Test Results

- `uv run pytest tests/` — 233 focused tests passed (session environment, subprocess, opencode, docker compose, settings), full suite green.
- `uv run ruff check .`, `ruff format --check .`, `uv run ty check`, `uv run bandit -c pyproject.toml .`, `uv run pre-commit run --all-files` — clean.
- `make check-compose` (`docker compose --env-file .env.docker config -q`) — valid.
- New/updated coverage: settings gate (no key ⇒ tracing off even when flag is true), platform key/project authoritative over project/user layers, layer values ignored, compose tracing default `false`.

## Follow-ups

- Rotate / authorize the `LANGSMITH_API_KEY` for the shared `Demetra` project and region; update the deployed host `.env.docker` (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`). Confirm traces appear in the single `Demetra` project after deploy.
- Tracing is now opt-in: turn it on deliberately only with a valid key. The earlier wiki follow-up about per-project `LANGSMITH_*` overrides is resolved — no project relies on them (confirmed by the resolve agent); one shared value is intentional.

## References

- Related: [[2026-09-28-compose-langsmith-host-env]]
- Related: [[2026-10-06-unify-subprocess-env-on-session-environment]]
- Related: [[2026-11-15-mnt-314-linear-mcp-static-api-key]]
- Code: `demetra/library/models.py:743`, `demetra/settings.py:243`, `demetra/services/runtime/subprocess.py:45`, `docker-compose.yaml:6`
