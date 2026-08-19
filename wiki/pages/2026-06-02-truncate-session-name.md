---
title: Truncate session name
date: 2026-06-02
type: implementation
status: resolved
session_id: "-"
services: [react]
branch: "-"
tickets: [MNT-92]
tags: [react, css, truncate, layout]
related: []
---

# Truncate session name

## TL;DR

Fixed a React layout bug where a long session name made the session list too tall and pushed the log console below it, breaking the intended left-right layout. The session item title box now fits within the session list using CSS truncation, following the existing `.session-plan` fixed-width pattern (120px, same width/font). Earlier PRs #43 and #44 were closed; the fix landed as part of the session-list rework (MNT-84 / MNT-59 sidebar).

---

## Overview

A long task title in the session list stretched the sidebar vertically, forcing the log console below the list instead of beside it. The fix constrains the title box and truncates the text with CSS.

- Session item title box fits within the session list
- CSS truncation for over-long names
- Original layout preserved (left sidebar + console)
- Follows the existing `.session-plan` fixed-width pattern (120px, same width/font)

## Step 1 — Constrain the title box

Updated the session item title box so it is bounded by the session list width instead of expanding to fit the full name.

## Step 2 — CSS truncation

Applied CSS truncation to the title so long names render as ellipsis rather than wrapping or expanding the row.

## Step 3 — Follow the `.session-plan` pattern

Reused the existing fixed-width pattern from `.session-plan` (120px, same width and font) so the sidebar layout stays consistent, keeping the left sidebar + console arrangement intact.

## Step 4 — Landing

The fix shipped as part of the session-list rework from MNT-84 / the MNT-59 sidebar rather than a standalone PR.

## Test Results

Tests were added/updated for the truncated session item layout.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-92
