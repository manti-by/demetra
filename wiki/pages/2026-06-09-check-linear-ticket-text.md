---
title: Check Linear ticket text
date: 2026-06-09
type: investigation
status: resolved
session_id: "-"
services: [linear, graphql, auth]
branch: "-"
tickets: [MNT-103, MNT-34, MNT-60]
tags: [linear, comments, research, oauth, tokens, graphql]
related: [2026-02-23-linear-oauth-2.0.md, 2026-03-11-separate-linear-comments.md]
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

## Source — [[2026-02-23-linear-oauth-2.0]]

Originally added in [[2026-02-23-linear-oauth-2.0]] on 2026-02-23 (MNT-34): the Linear
integration authenticates via **OAuth 2.0** (replacing a static header token) so
comments/updates are posted on behalf of a bot. The OAuth service handles token
persistence between runs, expiry validation before each use, and auto-refresh, and
every Linear API call is authorized dynamically through it. Credentials are
env-configurable: `LINEAR_CLIENT_ID` / `LINEAR_CLIENT_SECRET` in `demetra/settings.py`.
`--auto` CLI mode was added here.

## Source — [[2026-03-11-separate-linear-comments]]

Originally added in [[2026-03-11-separate-linear-comments]] on 2026-03-11 (MNT-60): a
`comments` field is bound to the Linear task model and synced via GraphQL (the sync
never deletes comments — it only reflects what Linear holds). `LinearTask.text`
includes the task's comments so downstream summarization and plan steps have the full
discussion context. Plan questions are posted as **individual Linear comments, one per
question**, instead of one aggregated comment — a human can answer each thread
individually. This is the model the comment rendering above builds on.

## Follow-ups

None.

## References

- Related: [[2026-02-23-linear-oauth-2.0]], [[2026-03-11-separate-linear-comments]]
- External: [MNT-103 — Check Linear ticket text (Linear)](https://linear.app/mnt/issue/MNT-103)
