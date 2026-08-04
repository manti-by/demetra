---
title: Check Linear ticket text
date: 2026-06-09
type: investigation
status: resolved
session_id: -
services: [linear, graphql]
branch: -
tickets: [MNT-103]
tags: [linear, comments, research]
related: []
---

# Check Linear ticket text

## TL;DR

Investigated what `LinearTicket.text` actually returns for resolved/unresolved comment threads, then used the findings to improve the Linear ticket renderer. Issues are now filterable by state, the issue list exposes branch name and labels, comments carry resolved status / timestamps / author names, nested replies are returned and organized, and tasks include label metadata. Researched against the Linear GraphQL explorer and implemented the renderer improvements.

---

## Net effect

Validated the GraphQL shape for ticket text and comments, then shipped an improved renderer that surfaces the newly-confirmed fields. The ticket view now shows branch name and labels on the issue list, and comment threads include resolved status, timestamps, author names, and nested replies.

## Step 1 — Validate `LinearTicket.text` output

Queried resolved and unresolved comments on the same ticket to confirm how the GraphQL API renders text. Verified the fields available on issue and comment nodes via the Linear GraphQL explorer (referenced artifact).

## Step 2 — Improve the renderer

**File:** `linear` service / issue list

The renderer was updated so the ticket list:

- filters issues by state,
- includes branch name and labels,
- renders comments with resolved status, timestamps, and author names,
- returns and organizes nested replies,
- carries label metadata on tasks.

## Step 3 — Supporting dev change

The watcher/log socket accepts a `token` query parameter in dev, so the frontend can authenticate websocket connections during development.

## Open questions

None — the research outcome was applied directly in the same PR.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-103 — Check Linear ticket text (Linear)](https://linear.app/mnt/issue/MNT-103)
