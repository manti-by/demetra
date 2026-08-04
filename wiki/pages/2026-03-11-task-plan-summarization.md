---
title: Task plan summarization
date: 2026-03-11
type: implementation
status: resolved
session_id: -
services: [groq, opencode]
branch: -
tickets: [MNT-61]
tags: [groq, llama, plan, summarization]
related: []
---

# Task plan summarization

## TL;DR

Replaced the fragile string-search/trim plan extraction with a cleaned, summarized plan: `extract_plan` moved to `demetra/services/groq.py` and now runs a LangChain chain (Groq + llama, markdown output) over the plan output plus the Linear task description and comments. The old `PLAN_HEADER_STRING` / `PLAN_IS_READY_STRING` / `PLAN_HAS_QUESTIONS` constants remain only for validation and prompt construction.

---

## Overview

The build step previously received a raw, messy plan scraped from agent output. Now it gets a concise, LLM-summarized plan that incorporates the task description and comments for a more complete implementation summary.

- `extract_plan` moved to `demetra/services/groq.py`
- LangChain chain with Groq + llama summarizing plan output + task description + comments
- Markdown output format
- Legacy header/is-ready/has-questions constants kept for validation/prompts

## Step 1 — Move `extract_plan`

**File:** `demetra/services/groq.py`

Relocated plan extraction into the Groq service so it sits with the other LLM summarization code.

## Step 2 — LangChain summarization chain

The chain summarizes the agent's plan output together with the Linear task description and its comments (from MNT-60), returning a clean markdown plan. Inputs outside the raw plan now shape the summary, so questions and context are preserved.

## Step 3 — Keep validation constants

The previous marker strings — `PLAN_HEADER_STRING`, `PLAN_IS_READY_STRING`, `PLAN_HAS_QUESTIONS` — are no longer used to parse the plan, but remain in use for validation and prompt construction.

## Test Results

Tests were added for the summarized plan extraction.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-61
