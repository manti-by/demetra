---
title: Session history — cached bundle and MCP tool usage
date: 2026-10-25
type: implementation
status: resolved
session_id: ses_e8b5aa148ffeyIlCo1dEIlSawZ
services: [api, agents/opencode, persistence/database, react, tests]
branch: "-"
tickets: []
tags: [session-history, tool-usage, mcp, opencode, code-mode, frontend, cost]
related: [2026-10-25-session-history-cost-and-failure-reasons.md, 2026-10-25-mnt-258-tool-usage-stats.md, 2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-opencode-v2-session-token-accounting.md]
---

# Session history — cached bundle and MCP tool usage

## TL;DR

Two user reports, one non-bug and one real gap. "Total Cost is missing from the
latest session" was a stale browser bundle — the API already returned
`total.cost = 1.147181502` for `df5bff3a` and the served
`index-1RxLK-wf.js` already contained the cell. The real defect: wiki/MCP calls
never appeared in Tool Usage because opencode v2 code mode runs MCP tools
*inside* the `execute` tool, and `_extract_tool_usage` only read top-level tool
parts — so every `WI.wiki_search` was persisted as `execute`. Extraction now
also counts `state.metadata.toolCalls`, which surfaces `WI.wiki_search` /
`WI.wiki_list_pages` / `Demetra.*` as their own rows through the existing DB →
API → React pipeline. No migration; 1041 backend + 21 frontend (component) tests
pass.

---

## Overview

Two follow-ups from the "Session history" modal shipped earlier today
([[2026-10-25-session-history-cost-and-failure-reasons]]): one about the
`Total Cost` cell and one about the Tool Usage block missing wiki calls. The
first needed diagnosis only; the second needed a code change in the opencode
export parser plus tests at the persistence and React layers.

## Step 1 — "No Total Cost" was a cached bundle, not a regression

**Files:** `demetra/api/sessions.py:87` (`_compute_total_tokens`),
`react/src/components/SessionHistory.tsx:149` (`TotalTokensBlock`)

Checked the three layers in order:

- **DB** — the latest session `df5bff3a-e9ed-45e0-a3ee-0274de2f8edf` has 23
  `kind='invocation'` rows with non-null `cost` (plan $0.0288, build $0.1042,
  reviews up to $0.1670), summing to ≈ $1.1472.
- **Live API** — `GET https://demetra.manti.by/api/v1/sessions/<task>/history`
  with a real auth cookie returns `total: {..., cost: 1.147181502}` (also direct
  against `api:8001`).
- **Served frontend** — nginx serves `/assets/index-1RxLK-wf.js`, byte-identical
  (same sha256) to `react/dist/assets/index-1RxLK-wf.js`, and that bundle
  contains `["$", l.cost.toFixed(4)]`.

Conclusion: deploy was current (built 18:24 UTC, commit `8e3f73e` at 18:04 UTC);
the user's tab was running the pre-deploy JS. Hard refresh fixed it. Two real
UX notes surfaced: the totals block renders *after* the timeline
(`SessionHistory.tsx:250`), so it sits below the fold with 25 cards, and
`kind='step'` rows intentionally carry no cost.

## Step 2 — MCP calls are hidden inside `execute`

**Files:** `demetra/services/agents/opencode.py:139` (`_nested_tool_calls`),
`:168` (`_count_tool_call`), `:186` (`_extract_tool_usage`)

opencode v2 code mode does not expose MCP tools as top-level tools — the model
calls `execute` with `tools["WI"].wiki_search(...)`. In a session export the MCP
calls are therefore a single `execute` part:

```json
{"type": "tool", "name": "execute",
 "state": {"status": "completed",
           "metadata": {"toolCalls": [
             {"tool": "WI.wiki_search", "status": "completed", "input": {"query": "relay schedule override", "limit": 10}},
             {"tool": "WI.wiki_list_pages", "status": "completed"}]},
           "time": {"created": 1792922515390, "completed": 1792922515400}}}
```

`_extract_tool_usage` read only `part["name"]` / `part["tool"]`, so the DB
recorded `execute` and the actual MCP names were lost. Evidence came from a real
Demetra plan session (`ses_e8bae76c...` for task `df5bff3a`): the export showed
`WI.wiki_search` + `WI.wiki_list_pages`, while `session_tool_usage` had only
`execute: 2`. Pre-code-mode history explains why this looked like it worked — the
local opencode DB still holds 20 `Demetra_wiki_search` and 15
`Demetra_wiki_get_page` **direct** MCP parts from Aug–Oct.

The fix reads both nestings (`state.metadata.toolCalls` in exports,
`state.metadata.metadata.toolCalls` in the CLI event stream), counts each nested
call under its own name, and keeps `execute` as the transport tool. Nested calls
have no timing, so `duration_ms` stays 0, and they inherit their part's
`invoked_at` watermark, which keeps fork-inherited plan calls out of build rows.

## Step 3 — Persistence and rendering needed no change

**Files:** `demetra/library/tables.py:200` (`session_tool_usage`),
`demetra/api/sessions.py:130` (`_compute_tool_usage`),
`react/src/components/SessionHistory.tsx:187` (`ToolUsageBlock`)

Validated the rest of the pipe rather than changing it:

- `session_tool_usage.tool_name` is `character varying` with no length limit, and
  the write path is name-agnostic — an insert of `WI.wiki_search` succeeded and
  was rolled back.
- `_compute_tool_usage` merges by name and orders by calls then name; dotted
  names pass through untouched.
- `ToolUsageBlock` renders `tool.name` verbatim in the 3-column grid and on
  invocation cards. Added `overflow-wrap: anywhere` to
  `.session-history-tool-name` and `.session-history-tool-grid dt`
  (`react/src/App.css:1800`) so long names such as
  `Demetra_get_table_definition` cannot overflow their cells.

Verified extraction against the real exports after the change: the plan session
now yields `WI.wiki_list_pages: 1`, `WI.wiki_search: 1` alongside `execute: 2`.

## Test Results

- `tests/test_opencode.py` — three new `TestExtractToolUsage` cases: nested
  `toolCalls` with mixed statuses, the CLI event-stream nesting, and the
  watermark dropping an out-of-range `execute` part with its nested calls.
- `tests/test_database.py::TestRecordToolUsage::test_mcp_tool_names_round_trip` —
  `WI.wiki_search` / `WI.wiki_list_pages` persist and read back through
  `record_agent_invocation`.
- `react/src/components/SessionHistory.test.tsx` — Tool Usage grid renders
  `WI.wiki_search` and `WI.wiki_list_pages` next to `execute` (21 component
  tests pass).
- Full backend suite: 1041 passed. The single failure,
  `tests/test_settings.py::TestSettings::test_opencode_defaults`, is
  environment-only — this container exports
  `OPENCODE_PATH=/usr/local/bin/opencode` while the test asserts the default
  path; it passes with the variable unset.
- `ruff check .`, `ty check`, `tsc --noEmit` clean.

---

## Follow-ups

- Existing `session_tool_usage` rows stay without MCP names — they were recorded
  before this fix. A backfill would have to re-run `_extract_tool_usage` over the
  stored session exports and respect each row's invocation watermark.
- The API/worker run uvicorn without `--reload`, so both need a restart to pick
  up the change.
- `execute` and its nested tools are both counted, so one code-mode call can add
  to several tool counters. The grid shows per-tool counts (no grand total), so
  this reads as transport + actual calls; revisit if a "total tool calls" figure
  is ever added.
- Session-history totals still sit below the timeline in the modal; a sticky or
  top-of-modal summary is the obvious UX follow-up.
- A live validation session (`ses_e8b4f7ec8ffek0ZWzRHOjQrgAO`, free
  `opencode/deepseek-v4.1-flash-free`, cost $0) was created to confirm a fresh
  `WI.wiki_search` call round-trips through export parsing.

## References

- Related: [[2026-10-25-session-history-cost-and-failure-reasons]] — shipped the
  `total.cost` cell and the step failure reasons this session verified live.
- Related: [[2026-10-25-mnt-258-tool-usage-stats]] — created the
  `session_tool_usage` table and the Tool Usage block whose extraction gap this
  session closed.
- Related: [[2026-10-16-mnt-251-session-attribution-accounting]] — the
  `kind='invocation'` rows and `invoked_at` watermark the nested calls inherit.
- Related: [[2026-10-16-opencode-v2-session-token-accounting]] — the opencode v2
  export shapes (`content`, `state.time`, `state.metadata`) this parser reads.
- External: user-reported inline; no Linear ticket.
