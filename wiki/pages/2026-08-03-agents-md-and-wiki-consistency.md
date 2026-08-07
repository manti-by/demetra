---
title: AGENTS.md Revalidation and Wiki Consistency Audit
date: 2026-08-03
type: implementation
status: resolved
session_id: ses_unknown
services: [docs, wiki, auth, workflow, mcp]
branch: wiki-context-integration
tickets: []
tags: [agents-md, wiki, consistency, documentation, context-metric]
related: [2026-07-23-agents-md-revalidation-and-docs-removal.md, 2026-07-23-session-tokens-audit-revalidation.md, 2026-08-03-check-api-auth-and-credentials.md, 2026-08-03-auth-hardening-and-deps-bump.md, 2026-07-16-fix-notification-mark-read.md, 2026-08-03-wiki-mcp-tools.md]
---

# AGENTS.md Revalidation and Wiki Consistency Audit

## TL;DR

Revalidated `AGENTS.md` against the current codebase (wiki section added, f-string
exception for `demetra/services/prompt.py`, underscore-helper naming ban confirmed, deps
moved to a `pyproject.toml`/`uv.lock` pointer, GitHub + Groq added to external deps, AI
Behavior condensed) and regenerated the `wiki/INDEX.md` "By topic" clusters from a fresh
consistency cross-check of all pages. Resolved two stale "not yet committed"/"build plan not
executed" claims by verifying the current master tree (PR #66 / #67 merged, `47d428d` landed),
leaving three still-open recommendations filed as follow-ups.

> **Status update (2026-08-04, Consistency Agent):** PR #68 has been merged into `master`
> (`ea754bc`, 2026-08-04); master has since advanced to `1.15.7` (was `1.15.5` when this
> page was written). The "open as PR #68" framing below is kept as the session record.
>
> **Status update (2026-08-06, Consistency Agent):** master has since advanced to `1.16.0`
> (PR #72, `99b5880`, MNT-146 post-build validation).

---

## Overview

Two related pieces of housekeeping, committed on the `wiki-context-integration` feature
branch and open as PR #68 against `master` (since merged):

1. **AGENTS.md** drift revalidation — bring the agent playbook back in line with the actual
   repo (MCP tool-module pattern, prompt.py f-string exception, underscore-prefix naming ban,
   dependency declarations, GitHub/Groq external deps).
2. **Wiki consistency** — re-cluster `wiki/INDEX.md` "By topic", and reconcile old pages that
   claimed their work was "uncommitted" / "not yet executed" against the now-merged master.

## Step 1 — AGENTS.md revalidation

**File:** AGENTS.md

- Added `wiki/` to the project-structure list plus a new "Wiki" section (read `INDEX.md`
  before planning; record each session under `wiki/pages/` via the `wiki-*` commands).
- Corrected the f-string rule to allow the sole exception: prompt-template substitution in
  `demetra/services/prompt.py`.
- Confirmed the blanket ban on `_`-prefixed functions stands: no private/underscore-prefixed
  function names; public functions stay unprefixed, CLI wrappers keep the
  `opencode_*`/`git_*`/`cursor_*` prefix.
- Replaced the hardcoded core/dev dependency lists with a pointer to `pyproject.toml` +
  `uv.lock` (the lists had drifted from `[dependency-groups]`).
- Documented **GitHub** and **Groq** in External Dependencies (with `demetra/listener.py` and
  `demetra/services/groq.py` as anchor refs).
- Condensed the "AI Behavior" bullets into one line.

## Step 2 — Wiki consistency cross-check and INDEX regen

**File:** wiki/INDEX.md

Re-clustered the `## By topic` section by semantic subject (largest first): new
"Authentication & API security (4)" cluster, "React frontend / UI (4)",
"Workflow state & retries (4)" (the notification/listener page moved here — the old
"Notifications & listener (1)" cluster was dropped), "Logging infrastructure (3)",
"Session history & tokens (2)", "Docs, feature flags & tooling (3)", "MCP / integrations (2)".
Fixed the `MAX_LISTENER_ATTEMPTS` summary text (default is now `5`, not `3`).

## Step 3 — Resolve stale claims against master

Verified the working tree and git history to correct outdated page statements:

- **File:** wiki/pages/2026-08-03-check-api-auth-and-credentials.md — the old
  "uncommitted on top of `a1e479d`" follow-up is now marked **done**: merged as PR #66
  (`8abcd8d`); the auth-filter/cors/mcp follow-up landed as PR #67 (`bcddc00`). Note: the Step 6
  bump to `1.16.0` was superseded — `5bcce84` shipped `1.15.5`.
- **File:** wiki/pages/2026-08-03-auth-hardening-and-deps-bump.md — added a status note that
  this change set was committed in `5bcce84` (MNT-156) and merged via PR #67 (`bcddc00`), with
  review fixes in `3d14f1d`; master is `1.15.5`, working tree otherwise clean.
- **File:** wiki/pages/2026-07-23-session-tokens-audit-revalidation.md — marked the build plan
  **done**: compaction is live at `demetra/workflows/build.py:79`, driven by the
  non-cumulative `context_tokens` metric (`demetra/services/opencode.py:225`,
  `usage.context = msg_input + msg_cache_read`), the `context_tokens`/`model` columns exist
  (`demetra/library/tables.py:114-115`), and the Groq input is capped at
  `PLAN_OUTPUT_MAX_CHARS = 32_000` (`demetra/services/groq.py:17,106`). All landed in `47d428d`.

## Test Results

- Verified all cited file:line anchors against the checked-out tree: `build.py:79` calls
  `check_and_compact_context`; `opencode.py:225` assigns `usage.context`; `tables.py:114-115`
  declare `context_tokens`/`model`; `groq.py` caps at `PLAN_OUTPUT_MAX_CHARS`.
- `git log`/`git status` confirm PR #66 (`8abcd8d`) and PR #67 (`bcddc00`) are merged and
  master is at `1.15.5`.
- No source-code or test changes; documentation-only edits. No lint/type/test gates affected.

---

## Follow-ups

- Still open from the audit recommendations: **#2** (cached reads still included in the
  compaction decision — `usage.context` at `demetra/services/opencode.py:225` adds
  `msg_cache_read`), **#3** (broad `except Exception` in
  `demetra/workflows/cleanup.py` and `demetra/services/groq.py:76,143`) and **#4** (no short-TTL
  cache on `opencode export`).
- The source-code companion to this page — the wiki MCP tools (`wiki_search`,
  `wiki_get_page`, `wiki_list_pages`) that AGENTS.md points agents to — is documented in
  [[2026-08-03-wiki-mcp-tools]].
- ~~Commit and PR these `AGENTS.md` + wiki edits (changes are currently staged/unstaged on
  `master`).~~ **Done** — committed on `wiki-context-integration`, merged as PR #68
  (`ea754bc`, 2026-08-04).

## References

- Related: [[2026-07-23-agents-md-revalidation-and-docs-removal]], [[2026-07-23-session-tokens-audit-revalidation]], [[2026-08-03-check-api-auth-and-credentials]], [[2026-08-03-auth-hardening-and-deps-bump]], [[2026-08-03-wiki-mcp-tools]]
- External: PR #66 (`8abcd8d`), PR #67 (`bcddc00`), commit `47d428d`