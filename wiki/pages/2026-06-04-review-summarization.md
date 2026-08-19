---
title: Review summarization
date: 2026-06-04
type: implementation
status: resolved
session_id: "-"
services: [groq, workflows, review, prompts, opencode]
branch: "-"
tickets: [MNT-98, MNT-41, MNT-61]
tags: [review, groq, llama, summarization, llm, parsing, testing, plan, build-plan]
related: [2026-02-26-create-llm-test-script.md, 2026-03-11-task-plan-summarization.md, 2026-08-18-migrate-llm-groq-to-openrouter.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md]
---

# Review summarization

## TL;DR

Review-agent findings are now summarized into one list by Groq + llama instead of being naively concatenated. A new prompt summarizes the review results; the simple `merge_review_results` was replaced with a Groq call using that prompt (behaving like the extract-questions chain — returning nothing when there are no questions/findings). Cases where thinking blocks were interpreted as review errors were removed; the workflow proceeds silently when there are no comments.

---

## Overview

Review agents return verbose, overlapping output. A Groq-powered summary produces one consolidated, deduplicated, numbered list of findings, with noise (no-issue lines) filtered out.

- New prompt to summarize review results
- `merge_review_results` replaced with a Groq + llama call using the summarization prompt
- Behaves like the extract-questions chain: returns nothing if no findings
- Thinking blocks no longer misinterpreted as review errors
- Review output consolidated, deduplicated, filtered of no-issue lines, presented as a numbered list
- Workflow proceeds silently when no comments

## Step 1 — Summarization prompt

Added a prompt that condenses all review-agent findings into a single summary list.

## Step 2 — Replace `merge_review_results`

**File:** `demetra/workflows/review.py`

Replaced the simple `merge_review_results` with a Groq call (llama) using the summarization prompt. Like the extract-questions chain, it returns nothing when there are no findings, so the workflow proceeds silently.

## Step 3 — Output quality

The consolidated output is deduplicated, filtered of no-issue lines, and presented as a numbered list. Removed cases where agent thinking blocks were interpreted as review errors.

## Test Results

Tests were added/updated for the summarized review output.

---

## Source — [[2026-02-26-create-llm-test-script]]

Originally added in [[2026-02-26-create-llm-test-script]] on 2026-02-26 (MNT-41): a
standalone LLM harness (LangChain + Groq) compares every LLM×parser combination —
chain type, LLM, and JSON parser — by running the real chain against a live Linear
ticket, writing results to `output/<llm>_<parser>.md`, then checking a test suite.
Run via `uv run main.py --test-llm`. This harness was used to drive the
summarization-chains work: MNT-61 (plan summarization) and MNT-98 (review
summarization) above were built and validated with it, which is why the 
Groq + llama pattern (chain, fallback, empty-on-no-findings) is consistent here.

## Source — [[2026-03-11-task-plan-summarization]]

Originally added in [[2026-03-11-task-plan-summarization]] on 2026-03-11 (MNT-61): the
plan agent's task-plan **summarization** moved into the Groq service
(`demetra/services/groq.py`) as an `extract_plan` Groq + llama chain that condenses the
plan (task description + comments from MNT-60) into a succinct build plan for Linear.
This supersedes the original local `extract_plan` in `opencode.py` (dating to MNT-20).
The `PLAN_IS_READY_STRING` / `PLAN_HAS_QUESTIONS` markers from MNT-30 are retained by
the chain so the workflow can branch on them. The review-summarization approach above
follows the same chain shape.

## Follow-ups

- None.

## Consistency note (2026-08-19)

- The LLM provider was migrated from Groq to OpenRouter on 2026-08-18 (MNT-168, see [[2026-08-18-migrate-llm-groq-to-openrouter]]). `summarize_review` now lives in `demetra/services/llm/openrouter.py`.
- `merge_review_results` was fully removed from the codebase; the review pipeline now concatenates agent outputs and passes them to `summarize_review()` directly.
- On LLM failure, `summarize_review` now raises `ReviewError` (routed to Awaiting Input via the `review_failed` template) instead of returning an empty list silently (see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]).

## References

- Related: [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]
- External: https://linear.app/mnt/issue/MNT-98
