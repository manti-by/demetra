---
title: Separate Linear comments
date: 2026-03-11
type: implementation
status: resolved
session_id: -
services: [linear, graphql]
branch: -
tickets: [MNT-60]
tags: [linear, comments, graphql]
related: []
---

# Separate Linear comments

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

Plan questions are now posted as individual Linear comments, one per question, rather than aggregated into a single comment.

## Test Results

Tests were added for the comment syncing and posting behavior.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-60
