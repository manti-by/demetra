---
title: Docstring MCP Search
date: 2026-09-08
type: implementation
status: resolved
session_id: -
services: [mcp, settings]
branch: delta/feature/docstring-mcp-search
tickets: []
tags: [docstrings, search, mcp, settings]
related: []
---

# Docstring MCP Search

## TL;DR

The MCP server can now search, list, and retrieve project function and method docstrings. The index is compiled in memory from Python syntax trees and is rebuilt only when source files change, avoiding repeated AST parsing for ordinary searches.

## Overview

**File:** demetra/tools/docstrings.py:1

`docstring_search`, `docstring_get`, and `docstring_list` expose function documentation under fully-qualified names such as `demetra.tools.wiki.call_tool`. Extraction uses `ast`, so it never imports project modules or runs their import-time side effects.

## Cache invalidation

**File:** demetra/tools/docstrings.py:126

The index fingerprint contains every source file's path, modification timestamp, and size. Searches reuse the compiled index until that fingerprint changes, then rebuild it to include additions, removals, and edits.

## Search configuration

**File:** demetra/settings.py:59

All shared search behavior is centralized in `SEARCH`: query limits, snippet limits, tokenization rules, stop words, and the wiki and docstring ranking weights. The wiki and docstring tools read this dictionary through `demetra.tools.search`, so their common behavior cannot drift.

## Test Results

- `uv run ruff check demetra/settings.py demetra/tools/docstrings.py demetra/tools/search.py demetra/tools/wiki.py tests/test_docstring_tools.py tests/test_wiki_tools.py`
- `uv run ruff format --check demetra/settings.py demetra/tools/docstrings.py demetra/tools/search.py demetra/tools/wiki.py tests/test_docstring_tools.py tests/test_wiki_tools.py`
- `uv run pytest tests/test_docstring_tools.py tests/test_wiki_tools.py`

---

## Follow-ups

- None.
