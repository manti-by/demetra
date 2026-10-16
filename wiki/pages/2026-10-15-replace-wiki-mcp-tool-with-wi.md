---
title: Replace the wiki MCP tool with WI and refactor demetra/tools
date: 2026-10-15
type: implementation
status: resolved
session_id: ses_ec053c1f0ffemU261xSI0EnbNh
services: [mcp, tools]
branch: master
tickets: []
tags: [mcp, tools, wiki, refactor, registry, corpus]
related: [2026-08-03-wiki-mcp-tools.md, 2026-10-09-bm25-search-for-mcp-tools.md]
---

# Replace the wiki MCP tool with WI and refactor demetra/tools

## TL;DR

The in-repo wiki MCP tool (`wiki_search` / `wiki_get_page` / `wiki_list_pages`,
`demetra/tools/wiki.py`) is retired — the wiki is served by the external **WI** MCP
server already wired into `opencode.json`. The rest of `demetra/tools` was then
restructured onto the layout of `manti-by/odin`'s `mcp_server`: shared
`models.py` / `config.py` / `corpus.py` / `utils.py`, a declarative
`MODULES` / `HANDLERS` registry, the misleadingly named `projects.py` renamed to
`logs.py`, and the previously dead `close_db_pool` wired into server shutdown.
Nine tools remain (three docstring, four database, two logs); 980 tests pass.

## Overview

Two changes, in order:

1. **Drop the wiki MCP tool.** The project already added a dedicated **WI** MCP
   server (`wi` command, `opencode.json:10-14`) that owns wiki search/read/list, so
   the in-repo duplicate is dead weight and a second implementation of the same
   corpus search to keep in sync.
2. **Refactor the whole `demetra/tools` package** to the shape of
   [manti-by/odin/mcp_server](https://github.com/manti-by/odin/tree/master/mcp_server):
   one module per concern (models, config, corpus, utils), a table-driven registry,
   and an entrypoint that releases the DB pool on exit. The database tool's
   denylist and `quote_ident` SQL were deliberately left unchanged — this pass is
   structural only.

## Step 1 — Remove the wiki MCP tool

**Deleted:** `demetra/tools/wiki.py` (417 lines) and `tests/test_wiki_tools.py`
(343 lines). The frontmatter parser and `PAGES_ROOT` stay in
`demetra/services/wiki/` — only the MCP wrapper is gone.

Cleanup the removal forced:

- `demetra/settings.py` — the six now-unused `SEARCH["wiki_*"]` boost/length-norm
  keys were deleted; `docstring_*` keys remain.
- `demetra/services/wiki/__init__.py` — `AGENTS_DRIFT_ANCHORS` no longer expects
  `demetra/tools/wiki.py` to appear in `AGENTS.md`
  (`check_agents_drift` returns anchors that are *missing*, so a stale path would
  have flagged every revalidation).
- `tests/conftest.py` — the autouse `isolate_wiki` fixture no longer patches the
  removed `demetra.tools.wiki` module; the `services/wiki` patches remain.
- `AGENTS.md` — the MCP server list and the External Dependencies table now name
  **WI** (and drop Playwright) to match `opencode.json`.

## Step 2 — Shared modules

Mirrors odin's `models.py` / `config.py` / `corpus.py` / `utils.py`:

- **`demetra/tools/models.py`** — `ToolResult`, `DocumentedFunction`, `Field`,
  `FieldCounts`, `CorpusStats`, moved out of `result.py` / `search.py` /
  `docstrings.py` so the dataclasses live in one place. `result.py` is deleted;
  `search.py` re-exports the three BM25 dataclasses, so `search.Field` still
  resolves for existing callers and tests.
- **`demetra/tools/config.py`** — `PROJECT_ROOT`, `SOURCE_ROOT`,
  `LOG_ROOT_DISPLAY`, `LOG_ROOT_RESOLVED`. Every project-specific path is derived
  here; tool modules no longer compute roots from `__file__`.
- **`demetra/tools/corpus.py`** — the substantive refactor. `docstrings.py`'s
  five loose cache globals (`_cached_fingerprint`, `_cached_functions`,
  `_cached_documents`, `_cached_stats`, `_cached_source_root`) are replaced by one
  frozen `Corpus[T]` snapshot published in a single assignment behind
  `CorpusCache[T]`, plus `Ranked[T]` and `rank()`. There is no window in which the
  items, field counts and statistics disagree, and callers cannot mutate the
  cached view.
- **`demetra/tools/utils.py`** — `resolve_limit`, the clamp the docstring tool
  previously inlined (and which raised on non-numeric input instead of falling
  back to the default).

## Step 3 — Registry

**File:** `demetra/tools/registry.py` — the old if/elif chain that eagerly called
`list_tools()` on each module to test membership is replaced by a declarative
table, matching odin:

```python
MODULES = (
    (database.list_tools, database.call_tool, database.AVAILABLE_TOOLS),
    (docstrings.list_tools, docstrings.call_tool, docstrings.AVAILABLE_TOOLS),
    (logs.list_tools, logs.call_tool, logs.AVAILABLE_TOOLS),
)
HANDLERS = {tool.name: handler for _, handler, tools in MODULES for tool in tools}
```

`call_tool` is now an `O(1)` dict lookup and returns the shared "Unknown tool"
error when the name is unregistered. Submodules are imported by path
(`import demetra.tools.database as database`) so the package `__init__` →
`registry` → submodule cycle stays broken.

## Step 4 — Tool modules

- **`docstrings.py`** — rewritten on `CorpusCache`; the dead `_fingerprint` helper
  is gone. Tested helpers are now public (`list_source_files`,
  `resolve_module_name`, `FunctionCollector`, `function_fields`, `load_functions`,
  `search_functions`, `extract_snippets`). Adopted odin's dot-expansion: the name
  field tokenizes `qualified_name.replace(".", " ")` and the query does the same,
  so searching `queue_task` reaches the highest-weighted field (previously only
  the docstring text matched).
- **`database.py`** — odin-shaped dispatch: an early `AVAILABLE_TOOLS_NAMES`
  membership check, one shared `table_name` validation for the three table tools,
  a `db_pool_lock` serializing the first `get_db_pool()` call, and
  `table_schema = 'public'` on `_get_table_columns`. The unused `auth_token`
  property on the `list_tables` schema was removed. `SENSITIVE_COLUMNS` and the
  `quote_ident()` queries are unchanged.
- **`projects.py` → `logs.py`** — renamed to match what it actually holds (log
  tools). `tail_file` takes odin's `complete()` fix so a truncated file can no
  longer return a partial first line, and `list_log_files` confines symlinks
  before reading metadata.
- **`mcp_server.py`** — `close_db_pool()` runs in a `finally` around the stdio
  loop. It was defined but never called, so the pool leaked on shutdown.

## Step 5 — Tests

- **Deleted** `tests/test_wiki_tools.py`.
- **Updated** `tests/test_docstring_tools.py` to the public helper names.
- **Added** `tests/test_tools_utils.py` (`resolve_limit` clamping and fallback)
  and `tests/test_tools_registry.py` (registry names match `HANDLERS`, schemas are
  object-typed, dispatch reaches the owning module).

## Test Results

- `ruff check` — clean across `demetra/tools`, `mcp_server.py`, `settings.py`,
  `services/wiki/__init__.py` and the touched tests.
- `ty check` — clean.
- **Full suite: 980 passed** (0.61s for the tool/search files alone). The suite
  needs a live Postgres: the local demetra Postgres was started via
  `docker compose up -d postgres` and the run pointed at it with
  `DB_HOST=localhost DB_PORT=54321 DB_USER=demetra DB_PASSWORD=demetra`.
- Tool surface: `list_tools()` now returns `docstring_get`, `docstring_list`,
  `docstring_search`, `get_table_count`, `get_table_definition`, `list_log_files`,
  `list_tables`, `query_table`, `tail_logs` — no `wiki_*`.

## Update — 2026-10-16 11:00

Follow-up pass on the same session, closing the doc and bookkeeping loose ends:

- **Doc accuracy.** `opencode.json` no longer defines `mcp.Playwright` — the
  slot now holds `mcp.servers.WI` (`"command": ["wi"]`). `AGENTS.md` was corrected to
  match: the `opencode.json` bullet reads MCP servers **Demetra/WI/Linear**, and
  the External Dependencies table lists **WI** (project wiki search/read/list via
  MCP) in place of the Playwright bullet. The previous text still pointed at an
  `mcp.Playwright` server that no longer exists.
- **Wiki bookkeeping.** The page was registered in `wiki/INDEX.md` — inserted at
  the top of `## Pages` and added to the `MCP & wiki tooling` cluster (12 → 13
  pages) — and mapped in `wiki/.sessions.json`. Update notes were appended to the
  two related pages (`2026-08-03-wiki-mcp-tools.md`,
  `2026-10-09-bm25-search-for-mcp-tools.md`).
- **Re-verified.** `ruff check .` and `ty check` clean; the focused tool/search
  suite is 53 passed (needs the demetra Postgres on `:54321`, started via
  `docker compose up -d postgres` and stopped afterwards). The running Demetra
  MCP server now advertises nine tools, matching the surface listed above.
- **V2 config migration.** `opencode.json` converted to the native V2 shape after
  the OpenCode 2 upgrade: `plugin` → `plugins`, the MCP servers moved under
  `mcp.servers` (V2 does not place server names directly under `mcp`), the V1
  `enabled: true` on each server dropped in favour of V2's inverse `disabled`
  (servers connect by default), and the `lsp` block removed — V2 accepts and
  preserves `lsp`, but runs no language servers and produces no diagnostics, so
  it was dead configuration (typing is already covered by `ty`/`ruff` in
  pre-commit and CI). Verified with `opencode mcp list` (v2.0.29): Demetra, WI
  and Linear all connect. Agent frontmatter (`permission`, `temperature`) is left
  as V1 — V2 translates it automatically and the rewrite is optional.
- **`wi` baked into the image.** The review on `opencode.json:12` flagged that the
  image configured `"command": ["wi"]` but never installed `wi`, so the server
  could not start in-container. The `Dockerfile` now runs the official `wi`
  installer in the builder stage into `/usr/local/bin` (pinned through a
  `WI_VERSION` build arg, default `v0.2.1`, with the installer itself fetched
  from that tag) and copies the binary into the final image next to `opencode`.
  `/usr/local/bin` is on the default `PATH`, so the stdio MCP transport starts as
  configured. Verified by installing the same way on the base image and driving a
  full stdio session (`initialize`, `tools/list`, all three tools, clean exit)
  with the `wi` repo's `mcp_smoke_stdio.py`.
- **OpenCode V2 in the image.** The `Dockerfile` installed the V1 client via
  `https://opencode.ai/install`; it now uses the V2 installer,
  `https://opencode.ai/v2/install`. Both write the same
  `$HOME/.opencode/bin/opencode`, so the existing `COPY … /usr/local/bin/opencode`
  (the path `OPENCODE_PATH` points at in `.env.docker.example`) is unchanged;
  verified in-image as `opencode v2.0.30`. Note the V2 client drops the V1
  `opencode export <id>` command (`session export` now) and the `run --dir` flag —
  `demetra/services/agents/opencode.py` still calls the V1 spellings, so those
  call sites need a follow-up pass.

## Follow-ups

- The database tool still uses a denylist (`SENSITIVE_COLUMNS`) plus
  `quote_ident()`; odin's deny-by-default `APPROVED_COLUMNS` allow-list was not
  ported in this pass (kept structural, per the session scope).

## References

- Reference layout — https://github.com/manti-by/odin/tree/master/mcp_server
- Registry — `demetra/tools/registry.py`
- Corpus cache — `demetra/tools/corpus.py`
- Related: [[2026-08-03-wiki-mcp-tools]]
- Related: [[2026-10-09-bm25-search-for-mcp-tools]]
