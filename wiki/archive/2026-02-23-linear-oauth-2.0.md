---
title: Linear OAuth 2.0
date: 2026-02-23
type: implementation
status: resolved
session_id: -
services: [linear, auth]
branch: -
tickets: [MNT-34]
tags: [linear, oauth, tokens]
related: []
---

# Linear OAuth 2.0

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-06-09-check-linear-ticket-text]]. See wiki/archive/ for the
> original.

## TL;DR

Linear header-token auth was replaced with OAuth 2.0 so comments/updates are posted on behalf of a bot. A new OAuth authorization service handles token persistence, expiry validation, auto refresh, and dynamic authorization of every Linear API call. A `--auto` CLI mode was added, and the review flow now runs multiple review agents and returns the first result.

---

## Overview

MNT-34 moves Linear integration from a static API header token to real OAuth 2.0, enabling bot-owned actions and long-lived, refreshable credentials configured via env vars.

## Step 1 — Add the OAuth authorization service

**File:** `demetra/services/` Linear auth

- token persistence (stored between runs)
- expiry validation before each use
- auto refresh when the token is near or past expiry
- every Linear API call is authorized dynamically through the service

## Step 2 — Configure OAuth credentials via env

**File:** `demetra/settings.py`

```python
LINEAR_CLIENT_ID     # from env
LINEAR_CLIENT_SECRET # from env
```

The README documents the OAuth setup flow (client registration, authorization, token storage).

## Step 3 — Add `--auto` CLI mode

**File:** `main.py`

`--auto` skips interactive prompts and chains review actions headlessly, complementing the existing flags.

## Step 4 — Review flow returns first result

The review flow runs multiple review agents and returns the first result, enabling unattended review in auto mode.

## Test Results

Verified through live runs posting comments and updates to Linear as the bot; refresh and re-auth paths exercised across token expiry.

---

## Follow-ups

None.

## References

- External: https://linear.app/mnt/issue/MNT-34
