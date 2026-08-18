---
title: Task plan summarization
date: 2026-03-11
type: implementation
status: resolved
session_id: -
services: [groq, opencode, workflows]
branch: -
tickets: [MNT-61]
tags: [groq, llama, plan, summarization, build-plan]
related: [2026-07-16-fix-empty-build-plan-loop.md]
---

# Task plan summarization

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-04-review-summarization]]. See wiki/archive/ for the
> original.

## TL;DR

Replaced the fragile string-search/trim plan extraction with a cleaned, summarized plan: `extract_plan` moved to `demetra/services/groq.py` and now runs a LangChain chain (Groq + llama, markdown output) over the plan output plus the Linear task description and comments. The old `PLAN_HEADER_STRING` / `PLAN_IS_READY_STRING` / `PLAN_HAS_QUESTIONS` constants remain only for validation and prompt construction. This supersedes the original `extract_plan()` in `demetra/services/opencode.py` from MNT-20 (`2026-02-21-add-plan-cleanup-middleware.md`).

---

## Overview

The build step previously received a raw, messy plan scraped from agent output. Now it gets a concise, LLM-summarized plan that incorporates the task description and comments for a more complete implementation summary.

- `extract_plan` moved to `demetra/services/groq.py`
- LangChain chain with Groq + llama summarizing plan output + task description + comments
- Markdown output format
- Legacy header/is-ready/has-questions constants kept for validation/prompts

## Step 1 — Original marker-trimming middleware (MNT-20)

**File:** `demetra/services/opencode.py`

The first approach added a plan-cleanup middleware step: `extract_plan()` searched for `PLAN_HEADER_STRING` / `PLAN_IS_READY_STRING` / `PLAN_HAS_QUESTIONS`, trimmed the surrounding agent chatter, and returned the clean plan body. It was called from `main.py` before the build step so the cleaned plan fed user-facing console messages, the Linear post, and the build prompt. Empty plans (no ready marker found) halted further processing — see [[2026-07-16-fix-empty-build-plan-loop]]. Tests in `tests/test_opencode.py` covered stored-plan reuse and empty-plan detection.

## Step 2 — Move `extract_plan`

**File:** `demetra/services/groq.py`

Relocated plan extraction into the Groq service so it sits with the other LLM summarization code.

## Step 3 — LangChain summarization chain

The chain summarizes the agent's plan output together with the Linear task description and its comments (from MNT-60), returning a clean markdown plan. Inputs outside the raw plan now shape the summary, so questions and context are preserved.

## Step 4 — Keep validation constants

The previous marker strings — `PLAN_HEADER_STRING`, `PLAN_IS_READY_STRING`, `PLAN_HAS_QUESTIONS` — are no longer used to parse the plan, but remain in use for validation and prompt construction.

## Test Results

Tests were added for the summarized plan extraction.

---

## Follow-ups

- None.

## References

- Related: [[2026-07-16-fix-empty-build-plan-loop]]
- External: https://linear.app/mnt/issue/MNT-61, MNT-20
