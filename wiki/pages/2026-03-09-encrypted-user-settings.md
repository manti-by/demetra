---
title: Encrypted user settings
date: 2026-03-09
type: implementation
status: resolved
session_id: -
services: [database, auth, api]
branch: -
tickets: [MNT-56]
tags: [encryption, user-settings, api]
related: []
---

# Encrypted user settings

## TL;DR

Added an encrypted `keys` field to the `User` model so per-user API keys and secrets can be stored at rest. Introduced `SECRET_KEY` and `ENCRYPTION_SALT` settings, a database field holding an encrypted JSON dict, and an API to update user data (currently just `keys`).

---

## Overview

Users need to store API credentials (e.g., LLM or tool keys) for their own sessions. Because these are sensitive, they are stored encrypted rather than as plaintext columns.

- `SECRET_KEY` + `ENCRYPTION_SALT` settings
- `User` database field storing an encrypted JSON dict
- API to update user data (currently only `keys`)
- Encryption used for storing API keys

## Step 1 — Settings

**File:** `demetra/settings.py`

Added `SECRET_KEY` and `ENCRYPTION_SALT` environment-driven settings used to derive the encryption key.

## Step 2 — Encrypted `keys` field

**File:** `demetra/library/models.py`

Added a `keys` field to the `User` model that stores an encrypted JSON dict. Encryption is applied before the value hits the database, so API keys are never stored in plaintext.

## Step 3 — User update API

Added an API endpoint to update user data. It currently accepts only the `keys` dict, but the shape leaves room for more user settings later.

## Test Results

Tests were added for the new user-update API.

---

## Follow-ups

- None.

## References

- External: https://linear.app/mnt/issue/MNT-56
