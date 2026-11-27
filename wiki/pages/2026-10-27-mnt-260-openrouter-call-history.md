---
title: 'MNT-260: Session calls to openrouter'
generated: {by: demetra, at: '2026-10-27T00:00:00Z'}
description: MNT-260 added OpenRouter LLM-call tracking to session history with kind='llm_call' rows from a new record_llm_call helper and token usage extracted from AIMessage metadata, threaded task_id through call sites, widened _compute_total_tokens and rendered LLM-call cards in the frontend, with all tests passing.
type: implementation
status: stable
session_id: ses_e82e0cbecffe1EX3fx64tzEyxJ
services: [api, llm, persistence, wiki, workflows]
branch: mnt-260-session-calls-to-openrouter
tickets: [MNT-260]
tags: [wiki, feature, backend]
related: [2026-10-25-session-history-per-invocation-rows.md, 2026-10-25-session-history-cost-and-failure-reasons.md, 2026-08-18-migrate-llm-groq-to-openrouter.md, 2026-11-24-mnt-321-external-providers-prices.md]
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
- Related: [2026-10-25-session-history-per-invocation-rows](/pages/2026-10-25-session-history-per-invocation-rows.md)
- Related: [2026-10-25-session-history-cost-and-failure-reasons](/pages/2026-10-25-session-history-cost-and-failure-reasons.md)
- Related: [2026-08-18-migrate-llm-groq-to-openrouter](/pages/2026-08-18-migrate-llm-groq-to-openrouter.md)
- Related: [2026-11-24-mnt-321-external-providers-prices](/pages/2026-11-24-mnt-321-external-providers-prices.md)

> **Consistency note (2026-11-11, Consistency Agent):** “Six functions were updated to accept a `task_id` parameter and call `_record_llm_call`” undercounts: there are now nine or more call sites in `demetra/services/llm/openrouter.py` (including `extract_errors` and `compose_wiki_page`).

> **Consistency note (2026-11-27, Consistency Agent):** OpenRouter `kind='llm_call'` rows now also carry USD `cost` and a `price` rate-card snapshot (`demetra/services/llm/openrouter.py:131`, `demetra/services/pricing.py`), added by [2026-11-24-mnt-321-external-providers-prices](/pages/2026-11-24-mnt-321-external-providers-prices.md).
