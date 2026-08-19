---
title: GitHub PR description
date: 2026-06-22
type: implementation
status: resolved
session_id: "-"
services: [groq, github]
branch: "-"
tickets: [MNT-115]
tags: [groq, pr, description]
related: [2026-08-18-migrate-llm-groq-to-openrouter.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md]
---

# GitHub PR description

## TL;DR

PRs created from a completed feature now get a real description instead of an empty/placeholder body. A Groq-backed service summarises what was done and the generated text is passed when creating the GitHub PR. Tests added.

---

## Overview

Before this change the GitHub PR body was empty or a placeholder. Now a summary of the work is generated and attached at PR creation.

## Step 1 — Build the description with Groq

**File:** `groq` service

Added a service that builds a PR description summarising what was done for the session/ticket.

## Step 2 — Pass it to GitHub PR creation

**File:** `github` service

When the PR is created, the generated text is used as the PR body, replacing the empty/placeholder description.

## Test Results

Tests cover the description-generation service and that the generated text is passed to PR creation.

---

## Follow-ups

None.

## Consistency note (2026-08-19)

- The LLM provider was migrated from Groq to OpenRouter on 2026-08-18 (MNT-168, see [[2026-08-18-migrate-llm-groq-to-openrouter]]). `generate_pr_description` now lives in `demetra/services/llm/openrouter.py`.
- On LLM failure, `generate_pr_description` now raises `PrDescriptionError` (routed to Awaiting Input) instead of returning an empty string silently (see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]).

## References

- Related: [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]
- External: [MNT-115 — GitHub PR description (Linear)](https://linear.app/mnt/issue/MNT-115)
