---
title: Linear link artifact
date: 2026-06-22
type: implementation
status: resolved
session_id: "-"
services: [database, api, react]
branch: "-"
tickets: [MNT-114]
tags: [linear-link, artifact, react]
related: []
---

# Linear link artifact

## TL;DR

Added a link to the Linear ticket in the session artifacts. A `linear_link` field was added to `sessions` with a migration; it is set on the first session save when the Linear task is retrieved, sent to the frontend, and shown in the session artifacts section as a "View Linear Issue" link. Tests on backend and frontend.

---

## Overview

The artifact block showed the PR link and build plan (MNT-108) but not the originating Linear ticket. This change adds the ticket link.

## Step 1 — Persist the linear link

**File:** `sessions` model + migration

Added a `linear_link` field to `sessions`. It is populated on the first session save once the Linear task is retrieved.

## Step 2 — Send it to the frontend

**File:** `api`

The session API returns `linear_link` alongside the other artifacts.

## Step 3 — Render the link

**File:** `react`

The session artifacts section now shows a "View Linear Issue" link that opens the ticket.

## Test Results

Tests cover the field population on first save, the API payload, and the rendered link.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-114 — Linear link artifact (Linear)](https://linear.app/mnt/issue/MNT-114)
