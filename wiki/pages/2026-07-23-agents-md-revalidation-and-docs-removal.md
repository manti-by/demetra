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

Updated `AGENTS.md` to reflect the current codebase (project description, MCP tool module pattern, feature flags, missing `langsmith` dep), deleted the now-redundant `DOCS.md` (391 lines, all content duplicated in AGENTS.md and wiki), added a new OpenCode command for automated AGENTS.md maintenance, and registered the LangSmith OpenCode plugin in `opencode.json`.

---

## Step 1 — New OpenCode command: `update-agents-file.md`

**File:** `.opencode/commands/update-agents-file.md` (new, 67 lines)

Created an OpenCode command definition that revalidates `AGENTS.md` against the current codebase, wiki pages, and git log. The command's build agent:

1. Reads AGENTS.md end-to-end and builds a mental index of every claim
2. Scans the wiki (INDEX.md + pages) for documented conventions
3. Verifies every claim against actual code (paths, modules, tooling, pyproject.toml)
4. Scans `git log --oneline -100` for renames, new modules, version bumps
5. Classifies drift as stale / missing / wrong
6. Applies fixes in place preserving section order and voice
7. Prints a grouped diff summary

## Step 2 — AGENTS.md updates

**File:** `AGENTS.md` — 4 changes:

1. **Project description** — "coding workflow orchestration tool" → "autonomous coding platform" (matches current positioning)
2. **MCP tool module pattern** — Updated from `create_<system>_tools(mcp)` factory pattern to the current `list_tools()` / `call_tool(name, arguments)` async module pattern aggregated via `demetra/tools/__init__.py`
3. **Feature flags section** — Added a new section documenting the `FEATURES` dict (`is_ruff_enabled`, `is_pytest_enabled`) with env vars and opt-in behavior from [[2026-07-22-feature-flag-settings-and-tests]]
4. **Dependencies** — Added `langsmith` to the core dependencies list (was already in `pyproject.toml` but missing from AGENTS.md)

## Step 3 — DOCS.md deletion

**File:** `DOCS.md` — deleted (391 lines)

`DOCS.md` was an extended developer documentation file that duplicated content now covered by `AGENTS.md` (conventions, git workflow, Linear workflow, dependencies, security) and the wiki (detailed project structure, environment variables, Makefile targets). All substantive content was already present in the wiki and AGENTS.md. Removing it eliminates a stale documentation source that was drifting out of sync.

## Step 4 — README.md link update

**File:** `README.md`

- Project description updated from "coding workflow orchestration tool" to "autonomous coding platform" (matching AGENTS.md)
- Link changed from `[DOCS.md](DOCS.md)` to `[Wiki](wiki/INDEX.md)` for development guidelines reference

## Step 5 — opencode.json: LangSmith plugin

**File:** `opencode.json`

Added `"plugin": ["@langchain/langsmith-opencode"]` to register the LangSmith OpenCode plugin for tracing and observability of OpenCode agent sessions.

## Step 6 — Wiki housekeeping

**Files:** `wiki/INDEX.md`, `wiki/QUESTIONS.md`

- **INDEX.md:** Title capitalization fix (`demetra` → `Demetra`)
- **QUESTIONS.md:** Removed resolved Q-002 about three overlapping ANSI stripping pages (the answer was already recorded and consolidation was completed by the Dedup Agent)

## Test Results

No test-impacting code changes. Lint/type/security checks are N/A for documentation-only changes.

---

## Follow-ups

- The `update-agents-file.md` OpenCode command should be invoked periodically (e.g., weekly or after major merges) to keep AGENTS.md accurate.
- Consider documenting the LangSmith plugin setup and tracing config in the wiki.

> **Status update (2026-08-27, Consistency Agent):** `.opencode/commands/update-agents-file.md`
> no longer exists. Commit `50755dd` ("Migrate commands to skills, fix allowlist") migrated all
> OpenCode commands to `.opencode/skills/<name>/SKILL.md` packages; this command's successor is
> `.opencode/skills/wiki-agents-file/SKILL.md` ("Update AGENTS.md"), which carries the same
> source-of-truth-priority (code > wiki > git log) revalidation flow described in Step 1.

> **Consistency note (2026-08-28, Consistency Agent):** Added missing `branch: "-"` frontmatter to match `wiki/TEMPLATE.md`.

## References

- Related: [[2026-07-22-feature-flag-settings-and-tests]]
- External: [LangSmith OpenCode plugin](https://github.com/langchain-ai/langsmith-opencode)
