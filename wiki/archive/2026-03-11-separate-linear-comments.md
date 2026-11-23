---
title: Separate Linear comments
generated: {by: demetra, at: '2026-03-11T00:00:00Z'}
description: Records MNT-60, which changed plan-question posting to one Linear comment per question instead of an aggregate and bound a GraphQL-synced, never-deleted `comments` field onto the Linear task model so `LinearTask.text` carries full discussion; the page was later archived and merged into the Linear-ticket-text page.
type: implementation
status: deprecated
session_id: '-'
services: [linear, graphql]
branch: '-'
tickets: [MNT-60]
tags: [linear, comments, graphql]
related: [2026-06-02-plan-loop-resolve-questions.md, 2026-06-09-check-linear-ticket-text.md]
---

# Separate Linear comments

> **Archived on 2026-09-28.** Useful info merged into
> [2026-06-09-check-linear-ticket-text](/archive/2026-06-09-check-linear-ticket-text.md). See wiki/archive/ for the
> original.

## TL;DR

Changed question posting so every found question becomes its own Linear comment instead of one aggregated comment, letting a human answer each one individually. Added data binding for a `comments` field on the Linear task model (GraphQL sync of all comments for a task into the model instance), comments are never deleted, and `LinearTask.text` now includes the task's comments.

---

## Overview

Before this change, all plan questions were bundled into a single comment. Splitting them into separate comments gives a human one thread per question to answer, and the synced `comments` field gives the workflow full visibility into existing discussion.

- `comments` field bound to the Linear task model, synced via GraphQL
- Comments are never deleted
- `LinearTask.text` includes the task's comments
- Questions posted as individual comments instead of one aggregated comment

## Step 1 — Comments data binding

**File:** `demetra/library/models.py`

Added a `comments` field to the Linear task model and synced all comments for a task into the model instance via a GraphQL query. The sync never deletes comments — the field only reflects what Linear holds.

## Step 2 — Text includes comments

Ensured `LinearTask.text` includes the task's comments so downstream summarization and plan steps have the full discussion context.

## Step 3 — One comment per question

Plan questions are now posted as individual Linear comments, one per question, rather than aggregated into a single comment. (Default mode; with `--plan-loop` they go to the resolve agent instead — see [2026-06-02-plan-loop-resolve-questions](/archive/2026-06-02-plan-loop-resolve-questions.md).)

## Test Results

Tests were added for the comment syncing and posting behavior.

---

## Follow-ups

- None.

> **Consistency fix (2026-09-18, Consistency Agent):** Quoted bare `session_id: -` / `branch: -` for valid YAML and mirrored body links into `related:` frontmatter.

## References

- Related: [2026-06-02-plan-loop-resolve-questions](/archive/2026-06-02-plan-loop-resolve-questions.md), [2026-06-09-check-linear-ticket-text](/archive/2026-06-09-check-linear-ticket-text.md)
- External: https://linear.app/mnt/issue/MNT-60
