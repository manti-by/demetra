---
title: GitHub PR description
date: 2026-06-22
type: implementation
status: resolved
session_id: -
services: [groq, github]
branch: -
tickets: [MNT-115]
tags: [groq, pr, description]
related: []
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

## References

- Related: none
- External: [MNT-115 — GitHub PR description (Linear)](https://linear.app/mnt/issue/MNT-115)
