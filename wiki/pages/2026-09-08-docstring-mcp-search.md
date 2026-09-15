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

MCP server now exposes `docstring_search`/`docstring_get`/`docstring_list` — ranked qualified names + snippets, full docstring by name, and catalog dump. Index built in-memory from `ast` (`_FunctionCollector` at `demetra/tools/docstrings.py:74`) without importing modules, cached via `(path, mtime_ns, size)` fingerprint. Same branch centralizes search config in `SEARCH` dict, hardens dispatcher, and reworks `bump_project_version` to explicit major/minor/patch. PR #120.

---

## Overview

**File:** `demetra/tools/docstrings.py:1` — `docstring_search` returns ranked `qualified_name` + source location + snippet; `docstring_get` returns full docstring; `docstring_list` dumps catalog. Names fully qualified (`module.Class.method`) from module path + scope. Definitions in `AVAILABLE_TOOLS` (`docstrings.py:228`), registered in `demetra/tools/registry.py:3` (`list_tools` concatenates database/docstring/project/wiki; `call_tool` routes by name).

## Cache invalidation — `demetra/tools/docstrings.py:45,125`

`_load_functions` fingerprints every Python source as `(relative path, mtime_ns, size)`; reuses index until fingerprint changes. Additions/removals/edits invalidate; unchanged tree → pure in-memory scan.

## Search config — `demetra/settings.py:59`

Shared `SEARCH` dict: query/result limits, snippet limits, tokenization rules, stop words, wiki + docstring ranking weights (`docstring_name_weight`, `docstring_path_weight`). Both tools tokenize via `demetra/tools/search.py:6` (`tokenize` extracted from wiki tool), so they cannot drift. Wiki scoring in `demetra/tools/wiki.py` reads same dict.

## Review fixes (2026-09-11) — `demetra/tools/docstrings.py:278`, `demetra/settings.py:62`

- `docstring_search` rejects non-string `query` and `len > SEARCH["max_query_length"]` (500) before work; schema advertises same `maxLength`.
- Dispatcher `except` also catches `AttributeError` (non-mapping `arguments` via `.get`) → tool error not propagation.
- New tests in `tests/test_docstring_tools.py`: `test_search_rejects_non_string_query`, `test_search_rejects_overlong_query`.

## Version bump rework (2026-09-11) — `demetra/services/runtime/project.py:328,331`

`bump_project_version` changed from fixed minor-only to explicit axis: `is_major`/`is_minor`/`is_patch` (default `is_patch=True`, so default now increments patch not minor). More significant flag clears lower ones (`is_major → major+1.0.0`, `is_minor → major.minor+1.0`). Renamed `_VERSION_PATTERN` → `PROJECT_VERSION_PATTERN`. Supersedes all-minor contract in [[2026-08-21-mnt-176-bump-version-error]] (`1.14.1 → 1.14.2` vs `→ 1.15.0`).

Two consumers **not** updated:

- Docstring (`project.py:334`) still says feature/bugfix bumps minor and patch resets.
- Workflow call site (`demetra/workflows/build.py:167`) still calls without `is_minor=True`, so auto bump silently switched minor→patch.

> Commit `dd4f152` on local branch, not in PR diff — confirm intended axis before merge.

## Test Results

- `ruff check` + `ruff format --check` on `settings.py`, `docstrings.py`, `search.py`, `wiki.py`, `test_docstring_tools.py`, `test_wiki_tools.py` — clean
- `pytest tests/test_docstring_tools.py tests/test_wiki_tools.py tests/test_project.py` — 45 passed (2026-09-11)

---

## Follow-ups

- Confirm `bump_project_version` default axis (patch vs minor) and whether callers expecting minor still pass `is_minor=True`.

> **Consistency note (2026-09-15, Consistency Agent):** Default bump axis `is_patch=True` verified against `demetra/services/runtime/project.py:331` and `demetra/workflows/build.py:167` (bare call → patch). Docstring at `project.py:334` still says minor — stale per 2026-09-08-docstring-mcp-search self-flag and Q-001 resolved 2026-09-11 (patch intentional). No wiki edit needed beyond this note.

## References

- Related: [[2026-08-03-wiki-mcp-tools]], [[2026-06-25-update-project-version]], [[2026-08-21-mnt-176-bump-version-error]]
- External: [PR #120](https://github.com/manti-by/demetra/pull/120)
