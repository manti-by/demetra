---
title: AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command
date: 2026-07-23
type: implementation
status: resolved
session_id: ses_unknown
services: [docs, opencode, settings]
branch: "-"
tickets: []
tags: [agents-md, documentation, opencode-commands, langsmith, feature-flags]
related: [2026-07-22-feature-flag-settings-and-tests.md]
---

# AGENTS.md Revalidation, DOCS.md Removal, and OpenCode Command

## TL;DR

Revalidated `AGENTS.md` against code/wiki/git-log (4 fixes), deleted redundant `DOCS.md` (391 lines, fully duplicated), added an OpenCode command for automated AGENTS.md maintenance, and registered the LangSmith plugin in `opencode.json`.

## Step 1 — New OpenCode command: `update-agents-file.md`

**`.opencode/commands/update-agents-file.md`** (67 lines) — revalidates AGENTS.md by: indexing every claim, scanning wiki/INDEX + pages, verifying against code (`pyproject.toml`, modules), checking `git log -100` for renames, classifying drift (stale/missing/wrong), fixing in place, printing grouped diff.

## Step 2 — AGENTS.md updates (4 changes)

1. Project description: "coding workflow orchestration tool" → "autonomous coding platform"
2. MCP pattern: `create_<system>_tools(mcp)` factory → `list_tools()`/`call_tool(name, arguments)` async modules via `demetra/tools/__init__.py`
3. Feature flags: new section for `FEATURES` dict (`is_ruff_enabled`/`is_pytest_enabled`) from [[2026-07-22-feature-flag-settings-and-tests]]
4. Dependencies: added `langsmith` (already in `pyproject.toml`)

## Step 3 — DOCS.md deletion (391 lines)

Extended dev docs duplicating AGENTS.md + wiki; removed to eliminate stale source. Content already in wiki/AGENTS.md.

## Step 4 — README.md

Description updated to match AGENTS.md; link `DOCS.md` → `wiki/INDEX.md`.

## Step 5 — `opencode.json`

Added `"plugin": ["@langchain/langsmith-opencode"]` for session tracing.

## Step 6 — Wiki housekeeping

- `wiki/INDEX.md`: `demetra` → `Demetra` capitalization.
- `wiki/QUESTIONS.md`: removed resolved Q-002 (ANSI stripping dedup done).

## Test Results

Docs-only; no test/lint impact.

## Follow-ups

- Invoke `update-agents-file` periodically (weekly / after major merges).
- Document LangSmith tracing setup in wiki.

> **Status update (2026-08-27):** `.opencode/commands/update-agents-file.md` migrated to `.opencode/skills/wiki-agents-file/SKILL.md` (commit `50755dd`, "Migrate commands to skills") — same revalidation flow (code > wiki > git log).

> **Consistency note (2026-08-28):** Added `branch: "-"` frontmatter.

## References

- Related: [[2026-07-22-feature-flag-settings-and-tests]]
- External: [LangSmith OpenCode plugin](https://github.com/langchain-ai/langsmith-opencode)
