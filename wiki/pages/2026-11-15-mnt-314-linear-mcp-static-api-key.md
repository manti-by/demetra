---
title: 'MNT-314 — Linear MCP static API key'
date: 2026-11-15
type: implementation
status: resolved
session_id: ses_e20a2d79affe7UhwTAmInRdV2Y
services: [agents, library, settings, tools, docker]
branch: opencode/feature/mnt-314-authenticate-linear-mcp-with-a-static-api-key
tickets: [MNT-314]
tags: [mcp, linear, oauth, api-key, environment, docker, opencode, secrets]
related: [2026-10-25-mcp-db-tools-env-sql.md, 2026-10-06-unify-subprocess-env-on-session-environment.md, 2026-08-10-process-environment-3-layers-encryption-uv-venv.md, 2026-09-28-compose-langsmith-host-env.md]
---

# MNT-314 — Linear MCP static API key

## TL;DR

The Linear MCP server no longer depends on an interactive OAuth consent the
containers cannot complete: `opencode.json` now sends a static
`Authorization: Bearer {env:LINEAR_API_KEY}` header with `oauth: false`, and
`LINEAR_API_KEY` resolves through the project → user-shared → system layers
like the OpenRouter and LangSmith keys. The Demetra MCP command lost its
cwd-relative `--env-file .env.docker` (which broke every clone and worktree),
non-secret `DB_*` defaults are forwarded to agent subprocesses, the MCP server
exits fast when `DB_PASSWORD` is missing from the encrypted env layers, and the
mounted host credential file is now derived into a provider-credentials-only
global config so host MCP sections cannot shadow the project. Verified: the
credential exposes 60 tools, Linear reports `connected` in the project root and
a worktree, and a fresh agent session called `Linear_get_issue` successfully.

---

## Overview

The ticket had four moving parts, all delivered in one branch:

- **Credential.** A read-write Linear personal API key against the full
  `https://mcp.linear.app/mcp` endpoint, sent as a Bearer header.
- **Environment layer.** The key reaches the agent subprocess through the
  existing `SessionEnvironment` resolver (project → user-shared →
  `settings.py`/system), never from a tracked file.
- **Demetra MCP command.** Removing `uv run --env-file .env.docker` fixes the
  server in clones and worktrees; `DB_*` now arrive through the same resolver.
- **Host credential file.** The compose mount is re-scoped to
  `providers.json`, and the entrypoint derives the global `opencode.json` with
  only `$schema` and `provider`.

## Step 1 — Credential probe

Before wiring anything, the key from the untracked `.env.docker` was probed
against the full endpoint over Streamable HTTP (`initialize` then
`tools/list`, `MCP-Protocol-Version: 2025-06-18`):

- `initialize` — HTTP 200, `serverInfo = {name: linear, version: 1.0.2}`
- `tools/list` — HTTP 200, **60 tools**
- Write surface present — `save_issue`, `save_comment`, `save_document`,
  `save_project`, `save_milestone`, `create_issue_label`, `delete_comment`, …
- Key fingerprint — `…5fO1`, 48 chars, never recorded in the ticket or repo

The same fingerprint decrypts from the existing encrypted
`LINEAR_API_KEY` project environment entry of the Demetra project, so no data
migration was needed locally.

## Step 2 — Static Bearer header in `opencode.json`

**File:** `opencode.json:14-21`

```json
"Linear": {
  "type": "remote",
  "url": "https://mcp.linear.app/mcp",
  "oauth": false,
  "headers": { "Authorization": "Bearer {env:LINEAR_API_KEY}" }
}
```

`oauth: false` is the OpenCode v2 switch that disables the discovery/PKCE
round-trip; with a header credential present it would otherwise try to
authenticate interactively.

## Step 3 — Supply the key through the environment layers

**File:** `demetra/settings.py:146` — `LINEAR["api_key"]` reads
`LINEAR_API_KEY` from the process environment, matching the other providers.

**File:** `demetra/library/models.py:513` — `settings_default()` maps
`LINEAR_API_KEY` to that setting, so `SessionEnvironment.lookup()` falls
through project → user-shared → system.

**File:** `demetra/library/models.py:710` — `system_env` forwards the resolved
`LINEAR_API_KEY` to every agent subprocess. A project value wins over a
user-shared value, which wins over `.env.docker`.

The key is stored encrypted already: `project_environment` carries
`LINEAR_API_KEY` (Demetra project) and the user scope carries one too; the API
masks both because `is_sensitive_key()` matches `*_KEY`. `.env.docker.example`
documents the system fallback without a real value.

## Step 4 — Remove the cwd-relative env file from the Demetra MCP

**File:** `opencode.json:6-9`

```json
"Demetra": { "type": "local", "command": ["uv", "run", "python", "-m", "demetra.mcp_server"] }
```

`--env-file .env.docker` is relative to the process cwd, so the server died in
every worktree and clone that had no `.env.docker`. `uv` now resolves the
project from the workspace itself.

To keep the database tools working without the file, `SessionEnvironment`
forwards the non-secret defaults:

- **File:** `demetra/library/models.py:486-492` — `settings_default()` maps
  `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_NAME`
- **File:** `demetra/library/models.py:711-714` — `system_env` forwards them

`DB_PASSWORD` is deliberately **not** forwarded from the system environment:
only the encrypted project/user entry reaches the subprocess.

## Step 5 — Fail fast without `DB_PASSWORD`

**File:** `demetra/mcp_server.py:80-81`

```python
if not DATABASE["password"]:
    raise RuntimeError("DB_PASSWORD environment variable is required")
```

The server now exits before opening the stdio transport instead of starting
with database tools that fail on first use.

## Step 6 — Provider-credentials-only global config

The host file was mounted directly at `~/.config/opencode/opencode.json`, so
any host section (MCP servers, agents, plugins, permissions) could shadow the
project config. Now:

- **File:** `docker-compose.yaml:30` — mounts
  `.keys/opencode/opencode.json` read-only as `providers.json`
- **File:** `configs/derive-opencode-config.py` — keeps only `$schema` and
  `provider`, rejects a non-object document/provider, writes atomically with
  `0600`
- **File:** `configs/docker-entrypoint.sh:6-13` — derives the real
  `opencode.json` at container start (root branch chowns it to `demetra`)
- **File:** `Dockerfile:68-69` — bakes the script into the image

## Test Results

- `uv run pytest tests/` — **1391 passed**
- `uv run ruff check .` — clean
- `uv run ty check` — clean
- `uv run pre-commit run --all-files` — all hooks pass
- New coverage: `tests/test_opencode_config.py` (MCP auth shape, no inlined
  key, no `--env-file`, derivation unit + CLI tests, compose mount/entrypoint),
  `tests/test_mcp.py` (fail-fast / startup), `tests/test_session_environment.py`
  (LINEAR_API_KEY and DB_* layer precedence, no system password forwarding)

## Verification

- `opencode mcp list` in the project root — `✓ Linear connected`
- `opencode mcp list` in a git worktree of the branch — `✓ Linear connected`
  and `✓ Demetra connected` (the env-file removal fixed the worktree spawn)
- Fresh agent session in that worktree
  (`opencode run --model opencode/deepseek-v4.1-flash-free`) — called
  `execute { tools.Linear.get_issue({ id: "MNT-314" }) }` and answered
  “Authenticate Linear MCP with a static API key”

---

## Follow-ups

- Rebuild the image and restart the app layer (`make deploy`) so the new
  entrypoint derivation and `opencode.json` take effect in containers.
- On a fresh database, seed `DB_PASSWORD` as an encrypted project or
  user-shared entry; the Demetra MCP server exits at startup without it by
  design. `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_NAME` keep their system defaults.
- The host provider file may contain any other OpenCode sections — they are
  intentionally dropped by the derivation; keep provider credentials there only.

## References

- Related: [[2026-10-25-mcp-db-tools-env-sql]]
- Related: [[2026-10-06-unify-subprocess-env-on-session-environment]]
- Related: [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Related: [[2026-09-28-compose-langsmith-host-env]]
- External: https://linear.app/mnt/issue/MNT-314/authenticate-linear-mcp-with-a-static-api-key
- External: https://opencode.ai/docs/mcp-servers/
