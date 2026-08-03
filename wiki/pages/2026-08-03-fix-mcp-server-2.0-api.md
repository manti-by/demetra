---
title: Fix MCP Server for the mcp 2.0 API
date: 2026-08-03
type: debug
status: resolved
session_id:
services: [mcp]
branch: master
tickets: []
tags: [mcp, dependencies, upgrade]
related: [2026-08-03-auth-hardening-and-deps-bump.md]
---

# Fix MCP Server for the mcp 2.0 API

## TL;DR

`uv run python -m demetra.mcp_server` crashed at import time with
`AttributeError: 'Server' object has no attribute 'list_tools'`. The `uv-bump` dependency
refresh ([[2026-08-03-auth-hardening-and-deps-bump]]) had pulled in `mcp 2.0.0`, which removed
the old `@server.list_tools()` / `@server.call_tool()` decorators from the low-level `Server`
and replaced them with `on_list_tools` / `on_call_tool` constructor callbacks. Rewrote
`demetra/mcp_server.py` against the new API and verified end-to-end over stdio
(initialize → tools/list → tools/call) plus the full test suite.

---

## Symptom

Running the MCP server fails before startup:

```console
$ uv run python -m demetra.mcp_server
AttributeError: 'Server' object has no attribute 'list_tools'
```

## Step 1 — Confirm the installed mcp version

`uv pip show mcp` reported **mcp 2.0.0**. Inspecting the new `Server` surface showed the
decorator-based registration methods are gone:

```text
['add_notification_handler', 'add_request_handler', 'create_initialization_options',
 'get_capabilities', 'get_notification_handler', 'get_request_handler', 'run',
 'server_info', 'server_info_stamp', 'session_manager', 'streamable_http_app']
```

## Step 2 — Find the new handler registration API

`mcp.server.lowlevel.Server.__init__` accepts `on_list_tools` and `on_call_tool` callables:

```text
on_list_tools: Callable[[ServerRequestContext, PaginatedRequestParams | None],
                        Awaitable[ListToolsResult]]
on_call_tool:  Callable[[ServerRequestContext, CallToolRequestParams],
                        Awaitable[CallToolResult | InputRequiredResult]]
```

Handler signatures changed too: the old handlers returned bare `list[Tool]` / `list[TextContent]`
and took positional `name`/`arguments`; the new ones must return `ListToolsResult` / `CallToolResult`
wrappers and take `(ctx, params)`.

## Root cause

The low-level mcp `Server` API was redesigned in 2.0.0 — decorator-based tool registration
(`@server.list_tools()`, `@server.call_tool()`) was removed in favor of constructor callbacks.
The code was written for the pre-2.0 API and broke the moment the dependency bumped.

## Resolution / Fix

**File:** `demetra/mcp_server.py`

before:
```python
from mcp.server import Server
from mcp.types import TextContent, Tool

mcp_server = Server(APP_NAME)

@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return await list_tools()

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    return await call_tool(name, arguments)
```

after:
```python
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.types import (
    CallToolRequestParams, CallToolResult,
    ListToolsResult, PaginatedRequestParams,
)

async def handle_list_tools(ctx, params) -> ListToolsResult:
    return ListToolsResult(tools=await list_tools())

async def handle_call_tool(ctx, params) -> CallToolResult:
    result = await call_tool(params.name, params.arguments)
    return CallToolResult(content=result.content, is_error=result.is_error)

mcp_server = Server(
    APP_NAME,
    version=VERSION,
    on_list_tools=handle_list_tools,
    on_call_tool=handle_call_tool,
)
```

Notes:
- `ServerRequestContext` imports from `mcp.server` (not `mcp.server.lowlevel`).
- Review follow-up (2026-08-03): the per-system `call_tool` dispatchers
  (`demetra/tools/database.py`, `demetra/tools/projects.py`) now return a shared `ToolResult`
  dataclass (`demetra/tools/result.py`) carrying `content` plus an `is_error` flag instead of a
  bare `list[TextContent]`. Validation failures, unknown tools, and backend exceptions set
  `is_error=True`, which `handle_call_tool` forwards into `CallToolResult.is_error` so MCP
  clients receive failed calls as errors rather than successful tool output. Only the
  protocol glue changed — the tool logic itself is untouched.
- `main()` and the `stdio_server()` loop were unaffected; `Server.run` keeps the same shape.

## Known follow-up

None for this bug. The mcp 2.0 upgrade also introduced high-level `MCPServer` (with
`@server.tool()`) which could simplify future tool registration, but the current dynamic
dispatcher pattern maps cleanly onto the low-level callbacks, so no migration is needed now.

---

## Follow-ups

- None.

## References

- Related: [[2026-08-03-auth-hardening-and-deps-bump]] (the `uv-bump` that pulled in mcp 2.0.0)
