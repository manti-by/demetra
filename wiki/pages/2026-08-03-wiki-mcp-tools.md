---
title: Wiki MCP Tools — Search, Read, and List Pages
date: 2026-08-03
type: implementation
status: resolved
session_id: ses_unknown
services: [wiki, mcp]
branch: wiki-context-integration
tickets: []
tags: [wiki, mcp, tools, knowledge-base, search]
related:
- 2026-08-03-agents-md-and-wiki-consistency.md
- 2026-08-03-fix-mcp-server-2.0-api.md
---

# Wiki MCP Tools — Search, Read, and List Pages

## TL;DR

Added `demetra/tools/wiki.py` exposing `wiki_search` / `wiki_get_page` / `wiki_list_pages` so agents can consult `wiki/pages/*.md` before answering about past incidents. Parses YAML frontmatter, weighted scorer, line-anchored snippets, path-traversal safe. Wired into `tools/__init__.py`, added `pyyaml`, bumped `1.15.5`→`1.15.6`, 28 tests. Merged as PR #68 (`ea754bc`).

## Overview

Backs AGENTS.md instruction "search the wiki first via `wiki_search`" ([[2026-08-03-agents-md-and-wiki-consistency]]). On `wiki-context-integration`, merged to `master` (now at `1.15.7`).

## Step 1 — `demetra/tools/wiki.py` (new)

Follows `async list_tools() -> list[Tool]` / `async call_tool(name, arguments) -> ToolResult` convention, aggregated by `tools/__init__.py`.

- **Frontmatter** (`_parse_page`): strips `---`, coerces bare `-` to `"-"`, `yaml.safe_load`; invalid/non-mapping → skip with warning, no frontmatter → `meta=={}`.
- **Search** (`_search_pages`): tokenizes (stop-word + single-char removal, keeps `mcp_server.py`-like terms), scores `10×title + 5×metadata + 1×body`, sorts descending, limit default 5 max 20.
- **Snippets** (`_extract_snippets`): top 3 body lines by hit count, 200-char truncation, `L<line>:` prefix, re-sorted to doc order.
- **Resolution** (`_resolve_page`): accepts `pages/`-prefixed / extension-less names, rejects traversal outside `PAGES_ROOT`.
- **Tools:** `wiki_search` (ranked name+title+snippets), `wiki_get_page` (full Markdown), `wiki_list_pages` (catalog, no bodies). All failures → `ToolResult(is_error=True)`.

## Step 2 — Aggregate wiring

**`demetra/tools/__init__.py`** — appends wiki tools to db+proj: `return db + proj + wiki`; routes `wiki_*` names to `tools.wiki.call_tool`.

## Step 3 — Deps + version

`pyproject.toml` + `uv.lock`: added `pyyaml>=6.0.3`, version `1.15.6` (from `1.15.5`).

## Step 4 — Tests

**`tests/test_wiki_tools.py`** (217 lines, 28 tests) — temp `pages/` with 2 pages, `monkeypatch PAGES_ROOT`. Covers: frontmatter (valid/absent/invalid/non-mapping/bare-dash), tokenizer, weighted ranking, snippet truncation, traversal rejection, every `call_tool` branch, aggregate registration via `tools.list_tools`/`call_tool`.

## Test Results

- `pytest tests/test_wiki_tools.py` — 28 passed (0.28s)
- `ruff check` clean; no other gates affected.

## Follow-ups

- ~~Commit + PR against `master`~~ **Done** PR #68 (`ea754bc`).
- Consistency/`wiki-*` commands now at `.opencode/skills/wiki-*/SKILL.md` (commit `50755dd` — commands→skills migration).

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [[2026-08-03-agents-md-and-wiki-consistency]], [[2026-08-03-fix-mcp-server-2.0-api]]
- External: AGENTS.md Wiki section (`wiki_search`/`wiki_list_pages`/`wiki_get_page`)
