---
title: Review summarization
date: 2026-06-04
type: implementation
status: resolved
session_id: -
services: [groq, workflows, review]
branch: -
tickets: [MNT-98]
tags: [review, groq, llama, summarization]
related: []
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

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-98
