---
title: "MNT-171: Docstring MCP search"
date: 2026-09-08
type: implementation
status: resolved
session_id: "-"
services: [mcp, settings, tools, runtime]
branch: delta/feature/docstring-mcp-search
tickets: [MNT-171]
tags: [docstrings, search, mcp, settings, version-bump]
related: [2026-08-03-wiki-mcp-tools.md, 2026-06-25-update-project-version.md, 2026-08-21-mnt-176-bump-version-error.md]
---

# MNT-171: Docstring MCP search

## TL;DR

The MCP server can now search, list, and retrieve project function and method docstrings through
`docstring_search`, `docstring_get`, and `docstring_list`. The index is compiled in memory from
Python syntax trees and rebuilt only when source files change, so ordinary searches never re-parse
the tree. The same branch centralizes wiki and docstring search settings in a shared `SEARCH` dict,
hardens the docstring search tool against malformed input, and reworks `bump_project_version` to
support explicit major/minor/patch bumps. PR
[#120](https://github.com/manti-by/demetra/pull/120) (`MNT-171`).

---

## Overview

**File:** `demetra/tools/docstrings.py:1`

`docstring_search` returns ranked qualified names, source locations, and matching docstring
snippets; `docstring_get` returns the full docstring by qualified name; `docstring_list` dumps the
catalog. Names are fully qualified, e.g. `demetra.tools.wiki.call_tool`, and are derived from the
module path plus class/function scope so methods are addressable as
`module.Class.method`. Extraction uses `ast` (`_FunctionCollector` at
`demetra/tools/docstrings.py:74`), so it never imports project modules or runs their import-time
side effects.

The three tool definitions live in `AVAILABLE_TOOLS` (`demetra/tools/docstrings.py:228`) and are
registered in `demetra/tools/registry.py:3` — `list_tools` concatenates the database, docstring,
project, and wiki tool lists, and `call_tool` routes by name to the owning module.

## Cache invalidation

**File:** `demetra/tools/docstrings.py:45`, `demetra/tools/docstrings.py:125`

`_load_functions` builds a fingerprint of every Python source file as
`(relative path, mtime_ns, size)` (`_fingerprint`) and reuses the compiled index until that
fingerprint changes. Additions, removals, and edits all invalidate it; searches against an
unchanged tree are pure in-memory scans.

## Search configuration

**File:** `demetra/settings.py:59`

All shared search behavior is centralized in the `SEARCH` dict: query/result limits, snippet
limits, tokenization rules, stop words, and the wiki and docstring ranking weights
(`docstring_name_weight`, `docstring_path_weight`). The wiki and docstring tools tokenize through
`demetra.tools.search.tokenize` (`demetra/tools/search.py:6`), which was extracted from the wiki
tool, so the two cannot drift. Wiki scoring in `demetra/tools/wiki.py` now reads the same dict.

## Review fixes (2026-09-11)

**File:** `demetra/tools/docstrings.py:278`, `demetra/settings.py:62`

Follow-up review hardening on the tool dispatcher:

- `docstring_search` rejects a non-string `query` and a query longer than
  `SEARCH["max_query_length"]` (500 chars) before doing any work; the schema advertises the same
  `maxLength`.
- The dispatcher's `except` clause also catches `AttributeError` (a non-mapping `arguments` could
  reach `.get`), so a malformed call returns a tool error instead of propagating.

New coverage in `tests/test_docstring_tools.py`: `test_search_rejects_non_string_query` and
`test_search_rejects_overlong_query`.

## Version bump rework (2026-09-11)

**File:** `demetra/services/runtime/project.py:328`, `demetra/services/runtime/project.py:331`

The branch also changes `bump_project_version` from a fixed minor-only bump to an explicit bump
axis: `is_major`, `is_minor`, `is_patch` flags (default `is_patch=True`, so the default call now
increments the patch, not the minor). Each more significant flag clears the lower ones, so
`is_major` yields `major+1.0.0`, `is_minor` yields `major.minor+1.0`, and the default yields
`major.minor.patch+1` while preserving any PEP 440 suffix. The private `_VERSION_PATTERN` was
renamed to the public `PROJECT_VERSION_PATTERN`.

This supersedes the all-minor contract from [[2026-08-21-mnt-176-bump-version-error]]; note the
default call site semantics changed (`1.14.1 → 1.14.2` instead of `1.14.1 → 1.15.0`).
`tests/test_project.py` now covers major, minor, and patch bumps.

Two consumers were **not** updated to match:

- The docstring (`demetra/services/runtime/project.py:334`) still says every feature/bugfix
  workflow bumps the minor version and that "the patch component is reset".
- The workflow call site (`demetra/workflows/build.py:167`) still calls
  `bump_project_version(target_path=...)` with no `is_minor=True`, so the automatic
  feature/bugfix bump silently switched from minor to patch.

> This commit (`dd4f152`) is on the local branch and was **not** in the PR diff at the time of
> this page. Confirm the intended bump axis with the release workflow before merge.

## Test Results

- `uv run ruff check demetra/settings.py demetra/tools/docstrings.py demetra/tools/search.py demetra/tools/wiki.py tests/test_docstring_tools.py tests/test_wiki_tools.py`
- `uv run ruff format --check demetra/settings.py demetra/tools/docstrings.py demetra/tools/search.py demetra/tools/wiki.py tests/test_docstring_tools.py tests/test_wiki_tools.py`
- `uv run pytest tests/test_docstring_tools.py tests/test_wiki_tools.py tests/test_project.py` — 45 passed (2026-09-11)

---

## Follow-ups

- Confirm the `bump_project_version` default axis (patch vs minor) is intended and that callers
  expecting a minor bump still pass `is_minor=True`.

## References

- Related: [[2026-08-03-wiki-mcp-tools]], [[2026-06-25-update-project-version]], [[2026-08-21-mnt-176-bump-version-error]]
- External: [PR #120](https://github.com/manti-by/demetra/pull/120)
