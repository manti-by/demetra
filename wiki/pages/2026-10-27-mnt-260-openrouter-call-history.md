---
title: 'MNT-260: Session calls to openrouter'
date: '2026-10-27'
type: implementation
status: resolved
session_id: ses_e82e0cbecffe1EX3fx64tzEyxJ
services: [api, llm/factory, llm/openrouter, persistence/database, wiki/render, workflows,
  pyproject, SessionHistory.test, SessionHistory, api.test, test_api, test_database,
  test_openrouter, test_tools_database, test_workflows, uv, INDEX, 2026-10-27-mnt-260-openrouter-call-history]
branch: mnt-260-session-calls-to-openrouter
tickets: [MNT-260]
tags: [wiki, feature, backend]
related: [2026-10-25-session-history-per-invocation-rows.md, 2026-10-25-session-history-cost-and-failure-reasons.md,
  2026-08-18-migrate-llm-groq-to-openrouter.md]
---

# MNT-260: Session calls to openrouter

## TL;DR
This session implemented the tracking of calls to OpenRouter in the session history, including the token usage. The implementation involved updating the OpenRouter services, API, and frontend to reflect these changes. All tests have passed, and the necessary Python files have been changed. A wiki page has also been added to document the changes.

## Overview
The goal of this implementation was to update the OpenRouter services to track calls in the session history and, if possible, track token usage. This required changes to the API and frontend as well.

## Step 1 — Update database.py to add record_llm_call function
**File:** `demetra/services/persistence/database.py`
The `record_llm_call` function was added to insert a new row into the `session_history` table with `kind="llm_call"` and extract token usage from the LangChain `AIMessage.response_metadata["token_usage"]`.

## Step 2 — Update openrouter.py to add _extract_usage and _record_llm_call helpers
**File:** `demetra/services/llm/openrouter.py`
The `_extract_usage` helper was added to read token usage from the `AIMessage.response_metadata`, and the `_record_llm_call` async helper was added to record LLM calls in the session history. Six functions were updated to accept a `task_id` parameter and call `_record_llm_call` after every `ainvoke`.

## Step 3 — Update factory.py to read model string from environment.openrouter_config
**File:** `demetra/services/llm/factory.py`
The `resolve_llm_model` function was updated to read the model string from the `environment.openrouter_config`.

## Step 4 — Update call sites to thread task_id parameter
**Files:** `demetra/workflows/plan.py`, `demetra/workflows/review.py`, `demetra/workflows/cleanup.py`, `demetra/services/wiki/render.py`
The `task_id` parameter was added to the call sites to thread the `task_id` parameter.

## Step 5 — Update sessions.py to include kind == "llm_call" rows in token sum
**File:** `demetra/api/sessions.py`
The `_compute_total_tokens` function was updated to include `kind == "llm_call"` rows in the token sum.

## Step 6 — Update frontend to render LLM-call cards with token/model/agent/cost grid
**Files:** `react/src/components/SessionHistory.tsx`, `react/src/services/api.ts`
The frontend was updated to render LLM-call cards with a token/model/agent/cost grid.

## Step 7 — Add tests
**Files:** `tests/test_openrouter.py`, `tests/test_database.py`, `tests/test_api.py`, `react/src/components/SessionHistory.test.tsx`, `react/src/services/api.test.ts`
Tests were added to verify the functionality of the changes.

## Test Results
All tests have passed, indicating that the implementation was successful.

## Follow-ups
- None

## References
- External: https://linear.app/mnt/issue/MNT-260/session-calls-to-openrouter
- Related: [[2026-10-25-session-history-per-invocation-rows]]
- Related: [[2026-10-25-session-history-cost-and-failure-reasons]]
- Related: [[2026-08-18-migrate-llm-groq-to-openrouter]]
