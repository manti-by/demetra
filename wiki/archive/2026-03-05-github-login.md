---
title: Add support for GitHub login
date: 2026-03-05
type: implementation
status: resolved
session_id: -
services: [auth, api, github]
branch: -
tickets: [MNT-48]
tags: [auth, github, oauth, jwt]
related: []
---

# Add support for GitHub login

> **Archived on 2026-08-18.** Useful info merged into
> [[2026-07-24-plain-auth-review-followups]]. See wiki/archive/ for the
> original.

## TL;DR

Added GitHub OAuth login to the FastAPI backend with secure token-based session management: endpoints for login, logout, and current-user, plus services to generate/retrieve/validate tokens and models to store auth data. A README section documents the integration setup. The React frontend was intentionally left untouched — that work landed separately in MNT-50.

---

## Overview

This ticket made GitHub the identity provider for Demetra's API. Prior to this, the app had no authenticated session concept; after it, API calls run under a validated user token.

- OAuth login flow for GitHub on the FastAPI app
- Token generation/retrieval/validation services
- Models to persist auth data
- Setup documentation in the README

## Step 1 — GitHub OAuth login APIs

**File:** `demetra/api.py`

Added endpoints backing the OAuth exchange plus session lifecycle:

- `login` — initiates/accepts the GitHub OAuth handshake
- `logout` — invalidates the current session
- `current-user` — returns the authenticated user for the session token

## Step 2 — Token services

Added services to generate, retrieve, and validate tokens for authenticated requests. Sessions are token-based (JWT), so every protected endpoint can verify the caller without a stateful session lookup.

## Step 3 — Auth models

Extended the data layer with models to store auth data (user + token records) so tokens can be persisted, looked up, and validated against the stored state.

## Step 4 — README setup section

Documented how to configure the GitHub OAuth integration (client credentials + callback wiring) so the app can be set up on a fresh environment.

## Test Results

Tests were added for the new token services and the auth API endpoints.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-48
