---
title: Add MCP server for the project
date: 2026-06-01
type: implementation
status: resolved
session_id: "-"
services: [mcp, database]
branch: "-"
tickets: [MNT-90]
tags: [mcp, streamable-http, filesystem, database]
related: [2026-08-03-fix-mcp-server-2.0-api.md]
---

# Add MCP server for the project

## TL;DR

Added a basic MCP server as a single standalone `mcp_server.py` in the project root, using the `mcp` PyPI package. It exposes streamable-http transport on a configurable port (env), filesystem tools with recursive access to the script's directory (CRUD for files/dirs), and PostgreSQL-only database tools for listing/reading tables and querying counts and rows — with no auth. The same change removed the hardcoded DB password default (env only) and bumped to 1.9.3.

---

## Overview

Demetra gains an MCP server so agents can inspect the project and its database over the Model Context Protocol. It was later rewritten for the mcp 2.0 API — see [[2026-08-03-fix-mcp-server-2.0-api]].

- Single standalone `mcp_server.py` in the project root
- Streamable-http transport on a configurable port (env)
- Filesystem tools: recursive access to the script's directory, CRUD for files/dirs
- Database tools: list/read tables and definitions, query table counts and rows — PostgreSQL only
- No auth
- Hardcoded DB password default removed (env only); version bumped to 1.9.3

## Step 1 — Standalone server

**File:** `mcp_server.py`

Added the MCP server as a single standalone script at the project root using the `mcp` PyPI package.

## Step 2 — Transport

Streamable-http transport served on a port configured via environment variable.

## Step 3 — Filesystem tools

Exposed filesystem tools with recursive access to the directory where the script lives, supporting CRUD operations on files and directories.

## Step 4 — Database tools

Exposed database tools — list tables, read table definitions, query table counts and rows — limited to PostgreSQL. No authentication is required to call them.

## Step 5 — Config cleanup

Removed the hardcoded DB password default so credentials come only from the environment, and bumped the version to 1.9.3.

## Follow-ups

- None.

## Consistency note (2026-08-20)

The server was relocated to `demetra/mcp_server.py` and now uses **stdio** transport (not streamable-http). Filesystem/database tools from this session were superseded by the aggregate tool registry in `demetra/tools/` — see [[2026-08-03-fix-mcp-server-2.0-api]] and [[2026-08-03-wiki-mcp-tools]].

---

## References

- Related: [[2026-08-03-fix-mcp-server-2.0-api]]
- External: https://linear.app/mnt/issue/MNT-90
