---
title: Markdown renderer
date: 2026-06-09
type: implementation
status: resolved
session_id: -
services: [react]
branch: -
tickets: [MNT-113]
tags: [react, markdown, marked, modal]
related: []
---

# Markdown renderer

## TL;DR

Added markdown-to-HTML rendering for the build plan in the React app using the `marked` library. A new button in the build-plan modal parses the raw markdown with `marked` and replaces it with the rendered HTML. Evidence: `marked` ^15.0.12 present in `react/package.json`; session record `daf47bca` ("MNT-113: Markdown renderer").

---

## Overview

The build-plan modal previously displayed raw markdown text. This change renders it as HTML for readability.

## Step 1 — Add the `marked` dependency

**File:** `react/package.json`

Added `marked` (^15.0.12) to the frontend dependencies.

## Step 2 — Render markdown in the build-plan modal

**File:** `react` build-plan modal

Added a button in the build-plan modal that:

- extracts the plan text,
- parses it with `marked`,
- replaces the original markdown with the rendered HTML.

## Test Results

Tests cover the render button and that the modal content switches from raw markdown to parsed HTML.

---

## Follow-ups

None.

## References

- Related: none
- External: [MNT-113 — Markdown renderer (Linear)](https://linear.app/mnt/issue/MNT-113)
