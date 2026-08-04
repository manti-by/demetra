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
related: [2026-08-03-agents-md-and-wiki-consistency.md, 2026-08-03-fix-mcp-server-2.0-api.md]
---

# Wiki MCP Tools — Search, Read, and List Pages

## TL;DR

Implemented the wiki MCP tools module `demetra/tools/wiki.py` exposing three tools —
`wiki_search`, `wiki_get_page`, `wiki_list_pages` — so agents can consult the session
knowledge base before answering questions about past incidents or design decisions. The
module parses YAML frontmatter, ranks pages with a title/metadata/body weighted scorer,
emits line-anchored snippets, and rejects path traversal. Wired into the aggregate
`demetra/tools/__init__.py` `list_tools`/`call_tool`, added `pyyaml` as a dependency,
bumped to 1.15.6, and covered with 28 tests.

> **Status update (2026-08-04, Consistency Agent):** PR #68 has been merged into `master`
> (`ea754bc`, 2026-08-04), so the `1.15.6` bump is on master; master has since advanced to
> `1.15.7` (`05cbff5`). The "open as PR #68" framing below is kept as the session record.

---

## Overview

`AGENTS.md` now instructs agents to "search the wiki first via the `wiki_search` MCP tool"
(see [[2026-08-03-agents-md-and-wiki-consistency]]). This change set is the tooling that
backs that instruction. Committed on the `wiki-context-integration` feature branch and open
as PR #68 against `master` (since merged):

1. New `demetra/tools/wiki.py` — three MCP tools over `wiki/pages/*.md`.
2. Aggregate wiring in `demetra/tools/__init__.py` (db + proj + wiki).
3. `pyyaml` dependency + version bump 1.15.5 → 1.15.6.
4. `tests/test_wiki_tools.py` — 28 tests across all layers.

## Step 1 — `demetra/tools/wiki.py` (new module)

**File:** demetra/tools/wiki.py

Follows the architecture convention from AGENTS.md: `async def list_tools() -> list[Tool]`
and `async def call_tool(name, arguments) -> ToolResult`, aggregated by the package-level
`demetra/tools/__init__.py`.

- **Frontmatter parsing** (`_parse_page`): strips the `---` block, coerces bare `-`
  placeholder values to `"-"` (so `branch: -` in the template parses), loads via
  `yaml.safe_load`; pages with invalid or non-mapping frontmatter are skipped with a
  logged warning, pages without frontmatter still work (`meta == {}`).
- **Search** (`_search_pages`): tokenizes the query (stop-word and single-char removal,
  keeps dotted/dashed terms like `mcp_server.py`), scores each page as
  `10 × title hits + 5 × metadata hits + 1 × body hits`, sorts descending, truncates to
  the requested limit (default 5, max 20).
- **Snippets** (`_extract_snippets`): the top 3 body lines by hit count, truncated to 200
  chars, prefixed `L<line>:`, and re-sorted into document order for readability.
- **Page resolution** (`_resolve_page`): accepts `pages/...`-prefixed and extension-less
  names, and rejects any name resolving outside `PAGES_ROOT` (path-traversal safe).
- **Tools**:
  - `wiki_search` — ranked page names + title/meta summary + snippets.
  - `wiki_get_page` — full Markdown body of one page by file name.
  - `wiki_list_pages` — catalog of every page with metadata, no bodies read.
- All failures return `ToolResult(is_error=True)` with a stable message; unexpected
  exceptions are logged via `logger.exception` and surfaced as a generic error.

## Step 2 — Aggregate wiring

**File:** demetra/tools/__init__.py

Appended the wiki tools to the existing db + projects aggregation:

```python
wiki = await _list_wiki_tools()
return db + proj + wiki
```

and routed `call_tool` by name: `wiki_*` names dispatch to `demetra.tools.wiki.call_tool`
before falling through to the projects module.

## Step 3 — Dependency and version bump

**File:** pyproject.toml, uv.lock

- Added `pyyaml>=6.0.3` to `dependencies` (used by frontmatter parsing) and regenerated
  `uv.lock` (`uv lock`).
- Bumped `version` to `1.15.6` (previous master version: `1.15.5`).

## Step 4 — Tests

**File:** tests/test_wiki_tools.py (new, 217 lines, 28 tests)

Fixtures build a temp `pages/` with two realistic pages and `monkeypatch` `PAGES_ROOT`.
Coverage: frontmatter parsing (valid, absent, invalid, non-mapping, bare-dash), tokenizer,
weighted ranking (title match outranks body match; body-only still found), snippet
selection/truncation, path resolution incl. traversal rejection, every `call_tool` branch
(list/search/get/error cases/missing directory), and aggregate registration through
`demetra.tools.list_tools` / `call_tool`.

## Test Results

- `uv run pytest tests/test_wiki_tools.py -q` — **28 passed** in 0.28s.
- `uv run ruff check demetra/tools/wiki.py demetra/tools/__init__.py tests/test_wiki_tools.py` — all checks passed.
- No other gates affected (no changes to services/workflows/api).

---

## Follow-ups

- ~~Commit and PR the staged changes (`AGENTS.md`, wiki tools, tests, dep bump) against
  `master`.~~ **Done** — committed on `wiki-context-integration`, merged as PR #68
  (`ea754bc`, 2026-08-04).
- The consistency/`wiki-*` commands in `.opencode/commands/` (e.g. `wiki-write.md`,
  `wiki-consistency.md`) are the manual companions to these tools; not reviewed this session.

## References

- Related: [[2026-08-03-agents-md-and-wiki-consistency]], [[2026-08-03-fix-mcp-server-2.0-api]]
- External: AGENTS.md "Wiki" section (`wiki_search` / `wiki_list_pages` / `wiki_get_page` usage)
