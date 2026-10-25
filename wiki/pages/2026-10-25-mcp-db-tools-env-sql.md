---
title: Fix the MCP database tools — missing env and broken SQL
date: 2026-10-25
type: debug
status: resolved
session_id: ses_e8b4cf16affeyLVQTq6NG6fUqQ
services: [mcp, tools, database, deploy, tests]
branch: -
tickets: []
tags: [mcp, database, asyncpg, environment, docker, uv-env-file, sql-injection, bandit, tooling]
related: [2026-10-15-replace-wiki-mcp-tool-with-wi.md, 2026-08-03-fix-mcp-server-2.0-api.md, 2026-06-01-add-mcp-server.md, 2026-08-10-process-environment-3-layers-encryption-uv-venv.md]
---

# Fix the MCP database tools — missing env and broken SQL

## TL;DR

Every Demetra MCP database tool answered `Error: Database operation failed`. The reported symptom was a missing `DB_PASSWORD` in the MCP server process — it is a child of `opencode serve --service`, which carries no `DB_*` variables, and `settings.DATABASE` reads only `os.environ` (the repo has no dotenv loader). Two real defects sat behind it: `get_table_count`/`query_table` built `FROM quote_ident($1)` (a scalar function in `FROM`, so count was always 1 and query returned a single fake row), and `query_table` numbered filter placeholders from `$2` while passing the table name as `$1`. Fixed the env wiring (`uv run --env-file .env.docker` plus `DB_HOST=postgres`), quoted validated identifiers inline, renumbered placeholders, and made `call_tool` surface the underlying exception. 1054 tests pass.

## Symptom

- `list_tables`, `get_table_definition`, `get_table_count` and `query_table` each returned `Error: Database operation failed` with `isError: true`.
- Non-database MCP tools (docstrings, logs) kept working, and the database was reachable from a shell with the same credentials, so the failure looked tool-specific rather than infra-wide.

## Step 1 — The MCP process had no database credentials

`/var/log/demetra/demetra.log` carried the real cause behind the generic message:

```
File "/srv/demetra/src/demetra/tools/database.py", line 61, in get_db_pool
    raise ValueError("DB_PASSWORD environment variable is required")
```

Evidence from the process tree: the MCP server (`python -m demetra.mcp_server`) is spawned by `uv run`, which is spawned by `opencode serve --service`. Its `/proc/<pid>/environ` contains `LINEAR_*`, `OPENROUTER_*` and `LANGSMITH_*` but **no `DB_*` keys at all**.

Why the database still looked healthy: OpenCode injects the project `.env` into shell-tool processes, so `uv run pytest` and manual `asyncpg` connections saw `DB_HOST`/`DB_USER`/`DB_PASSWORD`/`DB_NAME` while the MCP child did not.

Why nothing filled the gap: `demetra/settings.py:38-44` reads `DATABASE` straight from `os.environ` via `env_get_str` (host defaults to `localhost`, password to `None`), and no code path loads `.env` — `git log -S load_dotenv` is empty and `python-dotenv` is not a direct dependency.

## Step 2 — With credentials, `count` and `query` were still wrong

Running the tool functions in-process against the dev database:

- `get_table_count(pool, "projects")` returned `1` while `SELECT COUNT(*) FROM projects` returned `8`.
- `query_table(pool, "projects", limit=3)` returned `[{'quote_ident': 'projects'}]`.

Cause: PostgreSQL's `quote_ident()` is a scalar function returning `text`, so `FROM quote_ident($1)` is a one-row function scan, not a dynamic table reference. Identifiers cannot be bind parameters, so the validated name has to be quoted and interpolated. `list_tables` and `get_table_definition` were unaffected because they never interpolate a name into `FROM`.

## Step 3 — Fixing the quoting exposed a placeholder-offset bug

`query_table` had kept `params = [validated_name]` and built filters as `${i + 2}`, assuming the table name owned `$1`. Once the name moved inline, asyncpg raised `IndeterminateDatatypeError: could not determine data type of parameter $1` for every filtered query — the new tests caught it immediately.

## Root cause

Three independent defects stacked behind one opaque error string:

1. The MCP server process had no `DB_*` environment; `get_db_pool()` raised `ValueError`, which `call_tool` swallowed into the generic message.
2. `FROM quote_ident($1)` treated a scalar function as a table in both count and query paths.
3. `query_table` still numbered filter placeholders from `$2` after the table name stopped being a bind parameter.

## Resolution / Fix

- **`opencode.json:8`** — the Demetra MCP command is now `uv run --env-file .env.docker python -m demetra.mcp_server`. uv fills only variables that are not already set, so a host/CI env still wins over the file. `.env.docker` is mandatory for the server to spawn (`uv` errors on a missing env file).
- **`.env.docker:10` / `.env.docker.example:10`** — added `DB_HOST=postgres`. `.env.docker` defined only user/password/name, so the `localhost` default was applied and failed inside the container where Postgres is the `postgres` compose service. The `x-demetra-env` anchor in `docker-compose.yaml` already sets the same value per service, so compose behaviour is unchanged; the env file now also works for a standalone `uv run`.
- **`demetra/tools/database.py:232`** — new `_quote_identifier()` wraps a validated name in double quotes and escapes embedded quotes, mirroring `quote_ident()` in `demetra/services/runtime/project.py`.
- **`demetra/tools/database.py:272`** — `get_table_count` runs `SELECT COUNT(*) FROM "<table>"` instead of `FROM quote_ident($1)`.
- **`demetra/tools/database.py:302-310`** — `query_table` builds `SELECT * FROM "<table>"`, starts `params` empty, numbers filters with `len(params)`, then appends `LIMIT`/`OFFSET`; the `enumerate`/`i + 2` arithmetic is gone.
- **`demetra/tools/database.py:426-431`** — `call_tool` now returns `Error: Database operation failed: <exception>` so a client sees the cause without reading `/var/log/demetra/demetra.log`.
- **`pyproject.toml`** — `"demetra/tools/database.py" = ["S608"]` in ruff per-file ignores and `B608` in `[tool.bandit] skips`, both with a comment recording why: identifiers cannot be bind parameters, and names are validated by `TABLE_NAME_RE` plus the `information_schema` allow-list before being quoted. This is the config-level suppression the repo requires instead of inline `# noqa`/`# nosec`.
- **`tests/test_tools_database.py`** — 12 new tests: count correctness, real column projection, equality filters, limit/offset, sensitive-column stripping (`oauth_tokens`), unknown table/column rejection, and error propagation through `call_tool`. The query functions had no functional coverage before; `tests/test_tools_registry.py` only asserts the tool-definition surface.

## Test Results

- `pytest tests/` — **1054 passed** (`OPENCODE_PATH` unset; `tests/test_settings.py::TestSettings::test_opencode_defaults` asserts `.opencode` in the default path and fails whenever the container env sets `OPENCODE_PATH=/usr/local/bin/opencode`, which is unrelated to this change).
- `ruff check`, `ruff format`, `bandit -r demetra tests` and `pre-commit run --files` on the touched files — all clean.
- `ty check` — 1 diagnostic, the pre-existing `asynccontextmanager` deprecation in `demetra/services/wiki/index.py:43`.
- Manual stdio MCP handshake with `DB_*` stripped from the parent env: `get_table_count` → `{'table_name': 'projects', 'count': 8}` and `query_table` returned real project rows, confirming the `--env-file` path works without ambient credentials.

## Known follow-up (not fixed this session)

- The already-running MCP server keeps its old command and empty environment until OpenCode restarts it; the fix is not live in the session that reported the bug.
- `SENSITIVE_COLUMNS` matches column names exactly, so `users.password_hash` is **not** stripped by `query_table` (only `password`/`passwd` are).
- Making `.env.docker` load-bearing means a fresh clone without it loses *all* Demetra MCP tools at spawn time, not just the database ones.

---

## Follow-ups

- Restart the OpenCode server/session so the Demetra MCP server is respawned with `--env-file .env.docker`.
- Decide whether `password_hash` (and similar suffixed keys) should be covered by `SENSITIVE_COLUMNS`, or whether matching should become substring-based.
- Consider a launch fallback when `.env.docker` is absent, so the MCP server degrades to a clear per-tool error instead of failing to start.

## References

- Related: [[2026-10-15-replace-wiki-mcp-tool-with-wi]], [[2026-08-03-fix-mcp-server-2.0-api]], [[2026-06-01-add-mcp-server]], [[2026-08-10-process-environment-3-layers-encryption-uv-venv]]
- Source paths: `opencode.json`, `demetra/tools/database.py`, `demetra/settings.py`, `tests/test_tools_database.py`, `pyproject.toml`
