---
title: Fix MCP Server for the mcp 2.0 API
date: 2026-08-03
type: debug
status: resolved
session_id: "-"
services: [mcp, database]
branch: master
tickets: [MNT-90]
tags: [mcp, dependencies, upgrade, streamable-http, filesystem, database]
related: [2026-08-03-auth-hardening-and-deps-bump.md, 2026-06-01-add-mcp-server.md]
---

# Fix MCP Server for the mcp 2.0 API

## TL;DR

`mcp 2.0.0` (pulled by `uv-bump` in [[2026-08-03-auth-hardening-and-deps-bump]]) removed `@server.list_tools()`/`@server.call_tool()` decorators from low-level `Server`. `uv run python -m demetra.mcp_server` crashed at import with `AttributeError: 'Server' has no attribute 'list_tools'`. Rewrote `demetra/mcp_server.py` to use constructor callbacks `on_list_tools`/`on_call_tool` returning `ListToolsResult`/`CallToolResult`, and `ToolResult(is_error)` forwarding. Verified over stdio + full suite.

## Symptom

```
$ uv run python -m demetra.mcp_server
AttributeError: 'Server' object has no attribute 'list_tools'
```

`uv pip show mcp` → 2.0.0; `Server` surface now `add_notification_handler`, `add_request_handler`, `run`, `streamable_http_app` — no decorators.

## Root cause

mcp 2.0 redesigned low-level `Server` — decorator registration removed in favor of constructor callbacks with changed signatures (bare `list[Tool]` → `ListToolsResult`, `list[TextContent]` → `CallToolResult`, positional `name`/`arguments` → `(ctx, params)`).

## Resolution

**`demetra/mcp_server.py`:**

```python
# before
mcp_server = Server(APP_NAME)
@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]: return await list_tools()
@mcp_server.call_tool()
async def handle_call_tool(name, arguments) -> list[TextContent]: return await call_tool(name, arguments)

# after
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, PaginatedRequestParams

async def handle_list_tools(ctx, params) -> ListToolsResult:
    return ListToolsResult(tools=await list_tools())
async def handle_call_tool(ctx, params) -> CallToolResult:
    result = await call_tool(params.name, params.arguments)
    return CallToolResult(content=result.content, is_error=result.is_error)

mcp_server = Server(APP_NAME, version=VERSION, on_list_tools=handle_list_tools, on_call_tool=handle_call_tool)
```

Per-system dispatchers (`tools/database.py`, `tools/projects.py`) now return shared `ToolResult` (`tools/result.py`: `content` + `is_error`) — validation/unknown/backend errors set `is_error=True` forwarded to `CallToolResult.is_error`. Tool logic untouched; `main()`/`stdio_server()` unaffected.

## Follow-ups

None. High-level `MCPServer` with `@server.tool()` exists in 2.0 but no migration needed — dynamic dispatcher maps cleanly to low-level callbacks.

## Source — [[2026-06-01-add-mcp-server]]

First MCP server as repo-root `mcp_server.py` over streamable-http with filesystem+Postgres tools (MNT-90, 2026-06-01). Durable decisions: DB creds from env only, tool surface is DB/project introspection (filesystem tools deleted `e173d7f` 2026-06-02). Now at `demetra/mcp_server.py` over stdio, registry `tools/registry.py` aggregates `database`+`projects`+`wiki` via `ToolResult`.

## References

- Related: [[2026-08-03-auth-hardening-and-deps-bump]]
