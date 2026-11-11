---
title: 'MNT-258: Tool usage stats'
date: '2026-10-25'
type: implementation
status: resolved
session_id: ses_e8d0ccb3dffeMDtvKrTwEWduUG
services: [api, library, agents, persistence, vcs, workflows, database, migrations, react]
branch: mnt-258-tool-usage-stats
tickets: [MNT-258]
tags: [wiki, feature, backend, frontend]
related: [2026-10-16-mnt-251-session-attribution-accounting.md, 2026-10-16-opencode-v2-session-token-accounting.md, 2026-08-25-mnt-181-total-tokens-counter.md, 2026-07-23-session-history-modal.md, 2026-09-30-mnt-228-intermediate-history-states.md, 2026-10-25-session-history-per-invocation-rows.md, 2026-10-25-session-history-mcp-tool-usage.md]
---

# MNT-258: Tool usage stats

## TL;DR
This session implemented tool usage stats for the session history, adding a new table `session_tool_usage` to store per-tool call counts and extending the `SessionExport` model to include tool usage. The implementation correctly handles fork semantics, persists tool usage data, and updates the API to include tool usage in the session history response.

## Overview
The goal of this session was to add tool usage stats to the session history, allowing users to view the number of times each tool was used during a session. This required creating a new table to store the tool usage data, extending the `SessionExport` model, and updating the API to include tool usage in the session history response.

## Step 1 — Create a new table for tool usage data
A new table `session_tool_usage` was created to store per-tool call counts, with foreign keys referencing the `agent_sessions` table. This table will be used to accumulate tool usage data for each session.

> **Consistency note (2026-11-09, Consistency Agent):** this table was re-keyed two days later by [[2026-10-25-session-history-per-invocation-rows]] — its unique constraint is now `UniqueConstraint("history_id", "tool_name", name="uq_session_tool_usage_history")` (`demetra/library/tables.py:252`); the `agent_session_id` FK column remains. The opencode code-mode MCP-tool extraction gap closed afterwards is documented in [[2026-10-25-session-history-mcp-tool-usage]].

## Step 2 — Extend the SessionExport model
The `SessionExport` model was extended to include a `tool_usage` field, which will store the tool usage data for each session. This field will be populated with data from the `session_tool_usage` table.

## Step 3 — Update the API to include tool usage
The API was updated to include tool usage in the session history response. The `_compute_tool_usage` function was added to compute the tool usage for each session, and the `GET /{task_id}/history` endpoint was updated to include the tool usage data in the response.

## Step 4 — Persist tool usage data
The persistence layer was updated to write tool usage data to the `session_tool_usage` table. The `record_agent_invocation` function was updated to include tool usage data, and the `capture_agent_session` function was updated to write the tool usage data to the table.

## Step 5 — Handle fork semantics
The implementation correctly handles fork semantics by using a per-invocation `invoked_at` epoch-ms watermark to exclude pre-fork parent messages.

## Test Results
The implementation was tested, and the results show that the tool usage stats are correctly displayed in the session history.

## Follow-ups
- None

## References
- External: https://linear.app/mnt/issue/MNT-258/tool-usage-stats
- Related: [[2026-10-16-mnt-251-session-attribution-accounting]]
- Related: [[2026-10-16-opencode-v2-session-token-accounting]]
- Related: [[2026-08-25-mnt-181-total-tokens-counter]]
- Related: [[2026-07-23-session-history-modal]]
- Related: [[2026-09-30-mnt-228-intermediate-history-states]]

> **Consistency note (2026-11-11, Consistency Agent):** The `UniqueConstraint("history_id", "tool_name")` line reference is `demetra/library/tables.py:253` (the table starts at `:243`). The per-invocation `tool_usage` payload is written by `record_agent_invocation` (`demetra/services/persistence/database.py:1125-1140`).
