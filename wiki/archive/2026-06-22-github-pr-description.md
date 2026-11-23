---
title: GitHub PR description
generated: {by: demetra, at: '2026-06-22T00:00:00Z'}
description: Records MNT-115 generating GitHub PR descriptions from a Groq-backed LLM summary and attaching it as the PR body with tests; archived into the Groq-to-OpenRouter migration page after the service moved to `openrouter.py` and failures began raising `PrDescriptionError` into Awaiting Input.
type: implementation
status: deprecated
session_id: '-'
services: [llm, github]
branch: '-'
tickets: [MNT-115]
tags: [llm, pr, description]
related: [2026-08-18-migrate-llm-groq-to-openrouter.md, 2026-08-19-split-auth-linear-services-and-review-failure-handling.md]
---

# GitHub PR description

> **Archived on 2026-11-15.** Useful info merged into
> [2026-08-18-migrate-llm-groq-to-openrouter](/pages/2026-08-18-migrate-llm-groq-to-openrouter.md). See wiki/archive/ for the original.

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

- LLM migrated Groq → OpenRouter on 2026-08-18 (MNT-168, see [2026-08-18-migrate-llm-groq-to-openrouter](/pages/2026-08-18-migrate-llm-groq-to-openrouter.md)). `generate_pr_description` now in `demetra/services/llm/openrouter.py`.
- On LLM failure, raises `PrDescriptionError` (→ Awaiting Input) instead of returning empty string (see [2026-08-19-split-auth-linear-services-and-review-failure-handling](/pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md)).

> **Consistency fix (2026-09-18, Consistency Agent):** Mirrored body links into `related:` frontmatter.

## References

- Related: [2026-08-18-migrate-llm-groq-to-openrouter](/pages/2026-08-18-migrate-llm-groq-to-openrouter.md), [2026-08-19-split-auth-linear-services-and-review-failure-handling](/pages/2026-08-19-split-auth-linear-services-and-review-failure-handling.md)
- External: [MNT-115 — GitHub PR description (Linear)](https://linear.app/mnt/issue/MNT-115)

> **Consistency note (2026-11-11, Consistency Agent):** The `services:`/`tags:` frontmatter still listed `groq`, a service that no longer exists — `demetra/services/llm/` holds only `openrouter.py`, `parser.py`, `prompt.py` and `factory.py` (the Groq → OpenRouter migration is tracked in [2026-08-18-migrate-llm-groq-to-openrouter](/pages/2026-08-18-migrate-llm-groq-to-openrouter.md)). `generate_pr_description` now lives in `demetra/services/llm/openrouter.py:553` and still raises `PrDescriptionError` → Awaiting Input.
