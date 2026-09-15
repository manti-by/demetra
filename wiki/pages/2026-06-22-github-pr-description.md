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

PRs now get a generated description instead of an empty body: a Groq-backed service summarises the completed work and the text is passed as the GitHub PR body. Tests added.

---

## Overview

PR body was empty/placeholder. Now a summary is generated and attached at creation.

## Changes

- **Description generation** (`groq` service): builds a summary of what was done for the session/ticket.
- **PR creation** (`github` service): generated text used as PR body, replacing placeholder.

## Test Results

Tests cover description generation and that the text is passed to PR creation.

---

## Follow-ups

None.

## Consistency note (2026-08-19)

- LLM migrated Groq → OpenRouter on 2026-08-18 (MNT-168, see [[2026-08-18-migrate-llm-groq-to-openrouter]]). `generate_pr_description` now in `demetra/services/llm/openrouter.py`.
- On LLM failure, raises `PrDescriptionError` (→ Awaiting Input) instead of returning empty string (see [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]).

## References

- Related: [[2026-08-18-migrate-llm-groq-to-openrouter]], [[2026-08-19-split-auth-linear-services-and-review-failure-handling]]
- External: [MNT-115 — GitHub PR description (Linear)](https://linear.app/mnt/issue/MNT-115)
